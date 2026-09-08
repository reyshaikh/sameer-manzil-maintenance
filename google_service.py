import os
import json
import gspread
from google.oauth2.service_account import Credentials


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

        self.sheet = self.client.open(
            os.environ["GOOGLE_SHEET_NAME"]
        )

        self.resident_ws = self.sheet.worksheet(
            "Resident_Master"
        )

        self.receipt_ws = self.sheet.worksheet(
            "Receipts"
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
                "Maintenance Charges",
                d["Amount"]
            ])

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
