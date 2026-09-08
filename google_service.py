import json
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GoogleSheetService:
    def __init__(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        credentials_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=scopes,
        )

        self.client = gspread.authorize(credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)
        self.drive_folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
        self.sheet = self.client.open(os.environ["GOOGLE_SHEET_NAME"])

        self.resident_ws = self.sheet.worksheet("Resident_Master")
        self.payment_tracker_ws = self.sheet.worksheet("Payment_Tracker")
        self.charges_ws = self.sheet.worksheet("Charges_Master")
        self.receipt_ws = self.sheet.worksheet("Receipts")
        self.details_ws = self.sheet.worksheet("Receipt_Details")

    @staticmethod
    def _parse_month(month_name):
        return datetime.strptime(str(month_name).strip(), "%b-%Y")

    def get_residents(self):
        residents = []
        for row in self.resident_ws.get_all_records():
            status = str(row.get("Status", "")).strip().lower()
            if status in ("active", "yes", "y", ""):
                row["UnitNo"] = str(row.get("UnitNo", "")).strip()
                row["MobileNo"] = str(row.get("MobileNo", "")).strip()
                residents.append(row)
        return residents

    def get_payment_tracker(self):
        rows = self.payment_tracker_ws.get_all_records()
        for row in rows:
            row["UnitNo"] = str(row.get("UnitNo", "")).strip()
        return rows

    def get_charges(self):
        return self.charges_ws.get_all_records()

    def get_pending_months(self, unit_no):
        unit_no = str(unit_no).strip()
        today_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        for row in self.get_payment_tracker():
            if row.get("UnitNo") != unit_no:
                continue

            start_text = str(row.get("StartMonth", "")).strip()
            start_month = self._parse_month(start_text) if start_text else None
            pending = []

            for header, value in row.items():
                if header in ("UnitNo", "StartMonth"):
                    continue
                try:
                    month_date = self._parse_month(header)
                except ValueError:
                    continue
                if start_month and month_date < start_month:
                    continue
                if month_date > today_month:
                    continue
                if str(value).strip() == "":
                    pending.append(header)

            return sorted(pending, key=self._parse_month)

        return []

    def mark_months_paid(self, unit_no, months, receipt_no):
        unit_no = str(unit_no).strip()
        headers = self.payment_tracker_ws.row_values(1)
        records = self.payment_tracker_ws.get_all_records()

        for row_number, row in enumerate(records, start=2):
            if str(row.get("UnitNo", "")).strip() != unit_no:
                continue

            updates = []
            for month in months:
                if month in headers:
                    column_number = headers.index(month) + 1
                    updates.append(
                        {
                            "range": gspread.utils.rowcol_to_a1(row_number, column_number),
                            "values": [[receipt_no]],
                        }
                    )
            if updates:
                self.payment_tracker_ws.batch_update(updates)
            return

        raise ValueError(f"Unit {unit_no} not found in Payment_Tracker")

    def get_receipts(self):
        rows = self.receipt_ws.get_all_records()
        for row in rows:
            row["UnitNo"] = str(row.get("UnitNo", "")).strip()
            row["MobileNo"] = str(row.get("MobileNo", "")).strip()
        return rows

    def get_next_receipt_no(self):
        year = str(datetime.now().year)
        maximum = 0
        for row in self.get_receipts():
            parts = str(row.get("ReceiptNo", "")).split("-")
            if len(parts) == 3 and parts[1] == year:
                try:
                    maximum = max(maximum, int(parts[2]))
                except ValueError:
                    pass
        return f"REC-{year}-{maximum + 1:04d}"

    def save_receipt(self, receipt):
        self.receipt_ws.append_row(
            [
                receipt["ReceiptNo"],
                receipt["ReceiptDate"],
                receipt["UnitNo"],
                receipt["OwnerName"],
                str(receipt["MobileNo"]),
                receipt["PeriodFrom"],
                receipt["PeriodTo"],
                receipt["Months"],
                receipt["TotalAmount"],
                receipt["PaymentMode"],
                receipt["TransactionID"],
                receipt["PaymentStatus"],
                receipt["PDFFile"],
            ],
            value_input_option="USER_ENTERED",
        )

    def save_receipt_details(self, receipt_no, details):
        rows = [
            [receipt_no, detail["Particular"], detail["Amount"]]
            for detail in details
        ]
        if rows:
            self.details_ws.append_rows(rows, value_input_option="USER_ENTERED")

    def upload_pdf_to_drive(self, filepath):
        metadata = {
            "name": os.path.basename(filepath),
            "parents": [self.drive_folder_id],
        }
        media = MediaFileUpload(filepath, mimetype="application/pdf", resumable=False)
        uploaded = (
            self.drive_service.files()
            .create(body=metadata, media_body=media, fields="id,webViewLink", supportsAllDrives=True)
            .execute()
        )
        file_id = uploaded["id"]
        self.drive_service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True
        ).execute()
        return uploaded.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"

    def total_collection(self):
        return sum(float(row.get("TotalAmount", 0) or 0) for row in self.get_receipts())

    def pending_amount(self):
        total = 0.0
        for resident in self.get_residents():
            monthly = float(resident.get("MonthlyAmount", 0) or 0)
            total += len(self.get_pending_months(resident["UnitNo"])) * monthly
        return total
