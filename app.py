from datetime import datetime
from pathlib import Path
import os
import urllib.parse

from flask import Flask, flash, redirect, render_template, request, url_for, send_from_directory,session
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from google_service import GoogleSheetService


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "sameer-manzil-change-this")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
BASE = Path(__file__).resolve().parent
RECEIPTS = BASE / "receipts"
RECEIPTS.mkdir(exist_ok=True)

gs = GoogleSheetService()


def money(value):
    return f"₹{float(value or 0):,.2f}".replace(".00", "")


def next_receipt_no():
    return gs.get_next_receipt_no()


def generate_pdf(receipt, details):
    path = RECEIPTS / f"{receipt['ReceiptNo']}.pdf"
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=28,
        bottomMargin=28,
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], alignment=TA_CENTER, fontSize=16, leading=20)
    sub = ParagraphStyle("sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9)
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=9)

    story = [
        Paragraph("SAMEER MANZIL CO-OP. SOCIETY", title),
        Paragraph("Jeevan Baug, Mumbra, Dist. Thane - 400612", sub),
        Spacer(1, 8),
        Paragraph("<b>MAINTENANCE PAYMENT RECEIPT</b>", ParagraphStyle("h", parent=sub, fontSize=12)),
        Spacer(1, 10),
    ]

    info = [
        ["Receipt No", receipt["ReceiptNo"], "Date", receipt["ReceiptDate"]],
        ["Received From", receipt["OwnerName"], "Flat / Shop No", receipt["UnitNo"]],
        ["Mobile No", receipt["MobileNo"], "Maintenance Period", f"{receipt['PeriodFrom']} to {receipt['PeriodTo']}"],
    ]
    info_table = Table(info, colWidths=[80, 180, 95, 150])
    info_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f2f2")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f2f2f2")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([info_table, Spacer(1, 12)])

    rows = [["Sr. No.", "PARTICULARS", "Amount (₹)"]]
    for index, detail in enumerate(details, start=1):
        rows.append([str(index), detail["Particular"], f"{float(detail['Amount']):,.2f}"])
    rows.append(["", "TOTAL AMOUNT", f"{float(receipt['TotalAmount']):,.2f}"])

    charge_table = Table(rows, colWidths=[60, 335, 110])
    charge_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eaf2f8")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([charge_table, Spacer(1, 12)])

    payment = [
        ["Payment Status", "PAID"],
        ["Payment Mode", receipt["PaymentMode"]],
        ["Transaction ID", receipt["TransactionID"] or "Not Applicable"],
        ["Received By", "Society Office"],
        ["Generated On", datetime.now().strftime("%d-%b-%Y %I:%M %p")],
    ]
    payment_table = Table(payment, colWidths=[130, 375])
    payment_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f2f2")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            payment_table,
            Spacer(1, 18),
            Paragraph("This is a digitally generated receipt. Please retain it for future reference.", sub),
            Spacer(1, 28),
            Paragraph("For Sameer Manzil Co-op. Society<br/><br/>Secretary / Treasurer", right),
        ]
    )

    doc.build(story)
    return path.name
ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "sameer123"
)

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        if password == ADMIN_PASSWORD:

            session["admin"] = True

            return redirect(
                url_for("collection")
            )

        flash("Invalid Password")

    return render_template(
        "login.html"
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )

@app.route("/")
def home():
    residents = gs.get_residents()
    receipts = gs.get_receipts()
    total_collected = gs.total_collection()
    pending = gs.pending_amount()
    paid_units = len({row.get("UnitNo") for row in receipts if row.get("UnitNo")})
    return render_template(
        "home.html",
        total_units=len(residents),
        total_collected=total_collected,
        pending=pending,
        paid_units=paid_units,
        money=money,
    )


@app.route("/collection", methods=["GET", "POST"])
def collection():
    if not session.get("admin"):

        return redirect(
            url_for("login")
        )
    residents = gs.get_residents()
    charges = gs.get_charges()
    payment_tracker = gs.get_payment_tracker()

    if request.method == "POST":
        unit = request.form.get("unit", "").strip()
        selected_months = request.form.getlist("months")
        payment_mode = request.form.get("payment_mode", "Cash")
        transaction_id = request.form.get("transaction_id", "").strip()
        admin_password = request.form.get(
            "admin_password",
            ""
        )

        if admin_password != ADMIN_PASSWORD:

            flash(
                "Invalid Admin Password"
            )

            return redirect(
                url_for("collection")
            )
        resident = next((row for row in residents if str(row.get("UnitNo", "")).strip() == unit), None)
        if not resident:
            flash("Please select a valid unit.")
            return redirect(url_for("collection"))

        actual_pending_months = gs.get_pending_months(unit)
        valid_months = [month for month in selected_months if month in actual_pending_months]
        if not valid_months:
            flash("Please select at least one pending month.")
            return redirect(url_for("collection"))

        if payment_mode in ("UPI", "Bank Transfer", "Cheque") and not transaction_id:
            flash("Transaction or cheque number is required.")
            return redirect(url_for("collection"))

        monthly_amount = float(resident.get("MonthlyAmount", 0) or 0)
        details = [
            {"Month": month, "Particular": f"Maintenance {month}", "Amount": monthly_amount}
            for month in valid_months
        ]

        for charge in charges:
            charge_id = str(charge.get("ChargeID", "")).strip()
            charge_name = str(charge.get("ChargeName", "Additional Charge")).strip()
            amount_text = request.form.get(f"charge_amount_{charge_id}", "").strip()
            if not amount_text:
                continue
            try:
                charge_amount = float(amount_text)
            except ValueError:
                flash(f"Invalid amount for {charge_name}.")
                return redirect(url_for("collection"))
            if charge_amount > 0:
                details.append({"Particular": charge_name, "Amount": charge_amount})

        total_amount = sum(float(detail["Amount"]) for detail in details)
        receipt_no = next_receipt_no()
        now = datetime.now()

        receipt = {
            "ReceiptNo": receipt_no,
            "ReceiptDate": now.strftime("%d-%b-%Y"),
            "UnitNo": unit,
            "OwnerName": resident.get("OwnerName", ""),
            "MobileNo": str(resident.get("MobileNo", "")),
            "PeriodFrom": valid_months[0],
            "PeriodTo": valid_months[-1],
            "Months": ",".join(valid_months),
            "TotalAmount": str(total_amount),
            "PaymentMode": payment_mode,
            "TransactionID": transaction_id,
            "PaymentStatus": "Paid",
            "PDFFile": "",
        }

        pdf_file = generate_pdf(receipt, details)
        pdf_path = RECEIPTS / pdf_file

        try:
        
            receipt["PDFFile"] = gs.upload_pdf_to_drive(
                str(pdf_path)
            )
        
        except Exception as e:
        
            print(
                "Drive upload failed:",
                e
            )
        
            receipt["PDFFile"] = f"/receipts/{pdf_file}"
        
        gs.save_receipt(receipt)
        gs.save_receipt_details(receipt_no, details)
        gs.mark_months_paid(unit, valid_months, receipt_no)
        
        print(f"Receipt Generated: {receipt_no}"    )
        return redirect(url_for("receipt_result", receipt_no=receipt_no))

    return render_template(
        "collection.html",
        residents=residents,
        charges=charges,
        payment_tracker=payment_tracker,
    )


@app.route("/receipt/<receipt_no>")
def receipt_result(receipt_no):
    receipt = next(
        (row for row in gs.get_receipts() if str(row.get("ReceiptNo", "")) == receipt_no),
        None,
    )
    if not receipt:
        return "Receipt not found", 404

    mobile_digits = "".join(filter(str.isdigit, str(receipt.get("MobileNo", ""))))[-10:]
    mobile = "91" + mobile_digits
    message = (
        f"Dear {receipt.get('OwnerName', '')},\n\n"
        f"Your maintenance payment has been received.\n"
        f"Receipt No: {receipt.get('ReceiptNo', '')}\n"
        f"Amount: {money(receipt.get('TotalAmount', 0))}\n"
        f"Period: {receipt.get('PeriodFrom', '')} to {receipt.get('PeriodTo', '')}\n\n"
        f"Receipt link:\n{receipt.get('PDFFile', '')}\n\n"
        f"Regards,\nSameer Manzil Co-op. Society"
    )
    whatsapp_url = f"https://wa.me/{mobile}?text={urllib.parse.quote(message)}"
    return render_template("receipt_result.html", r=receipt, wa=whatsapp_url, money=money)

@app.route('/receipts/<path:filename>')
def download_receipt(filename):

    return send_from_directory(
        RECEIPTS,
        filename,
        as_attachment=False
    )
    
@app.route("/history")
def history():
    query = request.args.get("q", "").lower().strip()
    receipts = list(reversed(gs.get_receipts()))
    if query:
        receipts = [
            row
            for row in receipts
            if query in f"{row.get('ReceiptNo', '')} {row.get('UnitNo', '')} {row.get('OwnerName', '')}".lower()
        ]
    return render_template("history.html", receipts=receipts, money=money, q=query)


@app.route("/pending")
def pending():
    grouped = {}
    for resident in gs.get_residents():
        unit_no = resident["UnitNo"]
        months = gs.get_pending_months(unit_no)
        if not months:
            continue
        monthly = float(resident.get("MonthlyAmount", 0) or 0)
        grouped[unit_no] = {
            "owner": resident.get("OwnerName", ""),
            "months": months,
            "total": len(months) * monthly,
        }
    return render_template("pending.html", grouped=grouped, money=money)


@app.route("/google-test")
def google_test():
    return f"Connected Successfully: {gs.sheet.title}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
