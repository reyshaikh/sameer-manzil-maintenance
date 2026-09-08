import os
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GoogleSheetService:

    def __init__(self):
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds_dict = json.loads(
            os.environ["GOOGLE_CREDENTIALS"]
        )

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=scope
        )

        self.client = gspread.authorize(creds)
        self.drive_service = build(
            "drive",
            "v3",
            credentials=creds
        )
        
        self.drive_folder_id = os.environ[
            "GOOGLE_DRIVE_FOLDER_ID"
        ]

        self.sheet = self.client.open(
            os.environ["GOOGLE_SHEET_NAME"]
        )

        self.resident_ws = self.sheet.worksheet(
            "Resident_Master"
        )

        self.receipt_ws = self.sheet.worksheet(
            "Receipts"
        )

        self.payment_tracker_ws = self.sheet.worksheet(
            "Payment_Tracker"
        )
        
        self.charges_ws = self.sheet.worksheet(
            "Charges_Master"
        )

        
        self.dues_ws = self.sheet.worksheet(
            "Monthly_Dues"
        )

        self.details_ws = self.sheet.worksheet(
            "Receipt_Details"
        )

    
    
    # ---------------------------------
    # RESIDENTS
    # ---------------------------------

    def get_residents(self):
        rows = self.resident_ws.get_all_records()

        residents = []

        for row in rows:
            status = str(
                row.get("Status", "")
            ).strip().lower()

            if status in [
                "active",
                "yes",
                "y",
                ""
            ]:
                residents.append(row)

        return residents

    # ---------------------------------
    # DUES
    # ---------------------------------

    def get_dues(self):
        return self.dues_ws.get_all_records()

    def get_unpaid_dues(self):
        dues = self.get_dues()

        return [
            d for d in dues
            if str(
                d.get("Status", "")
            ).strip().lower() == "unpaid"
        ]

    def mark_due_paid(
        self,
        unit_no,
        months,
        receipt_no,
        payment_date
    ):
        records = self.dues_ws.get_all_records()

        for index, row in enumerate(records, start=2):

            if (
                row["UnitNo"] == unit_no
                and row["Month"] in months
            ):
                self.dues_ws.update(
                    f"D{index}:F{index}",
                    [[
                        "Paid",
                        receipt_no,
                        payment_date
                    ]]
                )

    # ---------------------------------
    # RECEIPTS
    # ---------------------------------

    def get_receipts(self):
        return self.receipt_ws.get_all_records()

    def get_next_receipt_no(self):

        receipts = self.get_receipts()

        year = str(
            __import__("datetime")
            .datetime.now()
            .year
        )

        max_number = 0

        for row in receipts:

            receipt_no = str(
                row.get(
                    "ReceiptNo",
                    ""
                )
            )

            try:

                parts = receipt_no.split("-")

                if (
                    len(parts) == 3
                    and parts[1] == year
                ):
                    value = int(parts[2])

                    if value > max_number:
                        max_number = value

            except:
                pass

        return (
            f"REC-{year}-"
            f"{max_number + 1:04d}"
        )

    def save_receipt(self, receipt):

        self.receipt_ws.append_row([
            receipt["ReceiptNo"],
            receipt["ReceiptDate"],
            receipt["UnitNo"],
            receipt["OwnerName"],
            receipt["MobileNo"],
            receipt["PeriodFrom"],
            receipt["PeriodTo"],
            receipt["Months"],
            receipt["TotalAmount"],
            receipt["PaymentMode"],
            receipt["TransactionID"],
            receipt["PaymentStatus"],
            receipt["PDFFile"]
        ])

    # ---------------------------------
    # RECEIPT DETAILS
    # ---------------------------------

    def save_receipt_details(
        self,
        receipt_no,
        dues
    ):

        for d in dues:

           self.details_ws.append_row([
                receipt_no,
                f"Maintenance {d['Month']}",
                d["Amount"]
         ])

    def upload_pdf_to_drive(self, filepath):

        filename = os.path.basename(filepath)
    
        metadata = {
            "name": filename,
            "parents": [self.drive_folder_id]
        }
    
        media = MediaFileUpload(
            filepath,
            mimetype="application/pdf"
        )
    
        file = (
            self.drive_service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id"
            )
            .execute()
        )
    
        file_id = file["id"]
    
        self.drive_service.permissions().create(
            fileId=file_id,
            body={
                "type": "anyone",
                "role": "reader"
            }
        ).execute()
    
        return f"https://drive.google.com/file/d/{file_id}/view"

        # ---------------------------------
    # PAYMENT TRACKER
    # ---------------------------------
    
    def get_payment_tracker(self):
    
        ws = self.sheet.worksheet(
            "Payment_Tracker"
        )
    
        return ws.get_all_records()
    
    
    def get_charges(self):
    
        ws = self.sheet.worksheet(
            "Charges_Master"
        )
    
        return ws.get_all_records()
    
    
    def get_pending_months(self, unit_no):
    
        ws = self.sheet.worksheet(
            "Payment_Tracker"
        )
    
        rows = ws.get_all_records()
    
        for row in rows:
    
            if str(row["UnitNo"]).strip() == str(unit_no).strip():
    
                pending = []
    
                for month, value in row.items():
    
                    if month in [
                        "UnitNo",
                        "StartMonth"
                    ]:
                        continue
    
                    if str(value).strip() == "":
                        pending.append(month)
    
                return pending
    
        return []
    
    
    def mark_months_paid(
        self,
        unit_no,
        months,
        receipt_no
    ):
    
        ws = self.sheet.worksheet(
            "Payment_Tracker"
        )
    
        headers = ws.row_values(1)
    
        records = ws.get_all_records()
    
        for row_num, row in enumerate(
            records,
            start=2
        ):
    
            if str(row["UnitNo"]).strip() == str(unit_no).strip():
    
                for month in months:
    
                    if month in headers:
    
                        col_num = headers.index(month) + 1
    
                        ws.update_cell(
                            row_num,
                            col_num,
                            receipt_no
                        )
    
                return
    
    # ---------------------------------
    # DASHBOARD
    # ---------------------------------

    def total_collection(self):

        receipts = self.get_receipts()

        return sum(
            float(
                r.get(
                    "TotalAmount",
                    0
                ) or 0
            )
            for r in receipts
        )

    def pending_amount(self):

        dues = self.get_dues()

        return sum(
            float(
                d.get(
                    "Amount",
                    0
                ) or 0
            )
            for d in dues
            if str(
                d.get(
                    "Status",
                    ""
                )
            ).lower() == "unpaid"
        )
