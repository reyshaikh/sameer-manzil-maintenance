from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from pathlib import Path
from datetime import datetime
import csv, os, urllib.parse
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from google_service import GoogleSheetService

gs = GoogleSheetService()

app = Flask(__name__)
app.secret_key = 'sameer-manzil-local-test'
BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
RECEIPTS = BASE / 'receipts'
RECEIPTS.mkdir(exist_ok=True)
RESIDENTS_FILE = DATA / 'residents.csv'
DUES_FILE = DATA / 'dues.csv'
RECEIPTS_FILE = DATA / 'receipts.csv'


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)
    os.replace(tmp, path)


def residents():
    return gs.get_residents()


def money(v):
    return f"₹{float(v):,.2f}".replace('.00','')


def next_receipt_no():
    return gs.get_next_receipt_no()


def generate_pdf(rec, selected_dues):
    path = RECEIPTS / f"{rec['ReceiptNo']}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    title = ParagraphStyle('title', parent=styles['Title'], alignment=TA_CENTER, fontSize=16, leading=20)
    sub = ParagraphStyle('sub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9)
    right = ParagraphStyle('right', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9)
    story=[]
    story.append(Paragraph('SAMEER MANZIL CO-OP. SOCIETY', title))
    story.append(Paragraph('Jeevan Baug, Mumbra, Dist. Thane - 400612', sub))
    story.append(Spacer(1,8))
    story.append(Paragraph('<b>MAINTENANCE PAYMENT RECEIPT</b>', ParagraphStyle('h', parent=sub, fontSize=12)))
    story.append(Spacer(1,10))
    info=[
        ['Receipt No', rec['ReceiptNo'], 'Date', rec['ReceiptDate']],
        ['Received From', rec['OwnerName'], 'Flat / Shop No', rec['UnitNo']],
        ['Mobile No', rec['MobileNo'], 'Maintenance Period', f"{rec['PeriodFrom']} to {rec['PeriodTo']}"]
    ]
    t=Table(info, colWidths=[80,180,95,150])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.grey),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#f2f2f2')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#f2f2f2')),('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),9),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOTTOMPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6)]))
    story.append(t); story.append(Spacer(1,12))
    rows = [
        [
            'Sr. No.',
            'PARTICULARS',
            'Amount (₹)'
        ]
    ]
    
    for index, detail in enumerate(
        selected_dues,
        start=1
    ):
    
        particular = (
            detail.get(
                'Particular'
            )
            or
            f"Maintenance {detail.get('Month', '')}"
        )
    
        rows.append(
            [
                str(index),
                particular,
                f"{float(detail['Amount']):,.2f}"
            ]
        )
    
    rows.append(
        [
            '',
            'TOTAL AMOUNT',
            f"{float(rec['TotalAmount']):,.2f}"
        ]
    )
    ct=Table(rows, colWidths=[60,335,110])
    ct.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.6,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1f4e78')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('ALIGN',(0,0),(0,-1),'CENTER'),('ALIGN',(2,1),(2,-1),'RIGHT'),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#eaf2f8')),('FONTSIZE',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7)]))
    story.append(ct); story.append(Spacer(1,12))
    payment=[['Payment Status','PAID'],['Payment Mode',rec['PaymentMode']],['Transaction ID',rec['TransactionID'] or 'Not Applicable'],['Received By','Society Office'],['Generated On',datetime.now().strftime('%d-%b-%Y %I:%M %p')]]
    pt=Table(payment,colWidths=[130,375])
    pt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.4,colors.grey),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#f2f2f2')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6)]))
    story.append(pt); story.append(Spacer(1,18))
    story.append(Paragraph('This is a digitally generated receipt. Please retain it for future reference.', sub))
    story.append(Spacer(1,28))
    story.append(Paragraph('For Sameer Manzil Co-op. Society<br/><br/>Secretary / Treasurer', right))
    doc.build(story)
    return path.name


@app.route('/')
def home():
    recs = gs.get_receipts()
    dues = gs.get_dues()
    total_units=len(residents())
    total_collected=sum(float(r['TotalAmount']) for r in recs if r.get('TotalAmount'))
    pending=sum(float(d['Amount']) for d in dues if d['Status']=='Unpaid')
    paid_units=len(set(r['UnitNo'] for r in recs))
    return render_template('home.html', total_units=total_units, total_collected=total_collected, pending=pending, paid_units=paid_units, money=money)

@app.route('/collection', methods=['GET', 'POST'])
def collection():

    residents_list = gs.get_residents()
    charges = gs.get_charges()
    payment_tracker = gs.get_payment_tracker()

    if request.method == 'POST':

        unit = request.form.get(
            'unit',
            ''
        ).strip()

        selected_months = request.form.getlist(
            'months'
        )

        payment_mode = request.form.get(
            'payment_mode',
            'Cash'
        )

        transaction_id = request.form.get(
            'transaction_id',
            ''
        ).strip()

        resident = next(
            (
                row for row in residents_list
                if str(
                    row.get(
                        'UnitNo',
                        ''
                    )
                ).strip() == unit
            ),
            None
        )

        if not resident:

            flash(
                'Please select a valid unit.'
            )

            return redirect(
                url_for(
                    'collection'
                )
            )

        actual_pending_months =
            gs.get_pending_months(
                unit
            )

        valid_months = [
            month
            for month in selected_months
            if month in actual_pending_months
        ]

        if not valid_months:

            flash(
                'Please select at least one pending month.'
            )

            return redirect(
                url_for(
                    'collection'
                )
            )

        if (
            payment_mode
            in (
                'UPI',
                'Bank Transfer',
                'Cheque'
            )
            and not transaction_id
        ):

            flash(
                'Transaction or cheque number is required.'
            )

            return redirect(
                url_for(
                    'collection'
                )
            )

        monthly_amount = float(
            resident.get(
                'MonthlyAmount',
                0
            ) or 0
        )

        receipt_details = []

        for month in valid_months:

            receipt_details.append(
                {
                    'Month': month,
                    'Particular':
                        f'Maintenance {month}',
                    'Amount': monthly_amount
                }
            )

        for charge in charges:

            charge_id = str(
                charge.get(
                    'ChargeID',
                    ''
                )
            ).strip()

            charge_name = str(
                charge.get(
                    'ChargeName',
                    'Additional Charge'
                )
            ).strip()

            amount_text = request.form.get(
                f'charge_amount_{charge_id}',
                ''
            ).strip()

            if not amount_text:
                continue

            try:

                charge_amount =
                    float(
                        amount_text
                    )

            except ValueError:

                flash(
                    f'Invalid amount for {charge_name}.'
                )

                return redirect(
                    url_for(
                        'collection'
                    )
                )

            if charge_amount > 0:

                receipt_details.append(
                    {
                        'Particular':
                            charge_name,
                        'Amount':
                            charge_amount
                    }
                )

        total_amount = sum(
            float(
                detail['Amount']
            )
            for detail in receipt_details
        )

        receipt_no =
            next_receipt_no()

        now =
            datetime.now()

        receipt = {

            'ReceiptNo':
                receipt_no,

            'ReceiptDate':
                now.strftime(
                    '%d-%b-%Y'
                ),

            'UnitNo':
                unit,

            'OwnerName':
                resident.get(
                    'OwnerName',
                    ''
                ),

            'MobileNo':
                str(
                    resident.get(
                        'MobileNo',
                        ''
                    )
                ),

            'PeriodFrom':
                valid_months[0],

            'PeriodTo':
                valid_months[-1],

            'Months':
                ','.join(
                    valid_months
                ),

            'TotalAmount':
                str(
                    total_amount
                ),

            'PaymentMode':
                payment_mode,

            'TransactionID':
                transaction_id,

            'PaymentStatus':
                'Paid',

            'PDFFile':
                ''
        }

        pdf_file = generate_pdf(
            receipt,
            receipt_details
        )

        pdf_path =
            RECEIPTS / pdf_file

        drive_link =
            gs.upload_pdf_to_drive(
                str(
                    pdf_path
                )
            )

        receipt['PDFFile'] =
            drive_link

        gs.save_receipt(
            receipt
        )

        gs.save_receipt_details(
            receipt_no,
            receipt_details
        )

        gs.mark_months_paid(
            unit,
            valid_months,
            receipt_no
        )

        return redirect(
            url_for(
                'receipt_result',
                receipt_no=receipt_no
            )
        )

    return render_template(

        'collection.html',

        residents
        
@app.route('/receipt/<receipt_no>')
def receipt_result(receipt_no):

    receipt = next(
        (
            row for row in gs.get_receipts()
            if str(
                row.get(
                    'ReceiptNo',
                    ''
                )
            ) == receipt_no
        ),
        None
    )

    if not receipt:
        return 'Receipt not found', 404

    mobile_digits = ''.join(
        filter(
            str.isdigit,
            str(
                receipt.get(
                    'MobileNo',
                    ''
                )
            )
        )
    )[-10:]

    mobile = '91' + mobile_digits

    message = (
        f"Dear {receipt.get('OwnerName', '')},\n\n"
        f"Your maintenance payment has been received.\n"
        f"Receipt No: {receipt.get('ReceiptNo', '')}\n"
        f"Amount: {money(receipt.get('TotalAmount', 0))}\n"
        f"Period: {receipt.get('PeriodFrom', '')} "
        f"to {receipt.get('PeriodTo', '')}\n\n"
        f"Receipt link:\n"
        f"{receipt.get('PDFFile', '')}\n\n"
        f"Regards,\n"
        f"Sameer Manzil Co-op. Society"
    )

    whatsapp_url = (
        f"https://wa.me/{mobile}"
        f"?text={urllib.parse.quote(message)}"
    )

    return render_template(
        'receipt_result.html',
        r=receipt,
        wa=whatsapp_url,
        money=money
    )

@app.route('/receipts/<path:filename>')
def download_receipt(filename):
    return send_from_directory(RECEIPTS, filename, as_attachment=True)

@app.route('/history')
def history():
    q=request.args.get('q','').lower().strip(); recs=list(reversed(gs.get_receipts()))
    if q: recs=[r for r in recs if q in (r['ReceiptNo']+' '+r['UnitNo']+' '+r['OwnerName']).lower()]
    return render_template('history.html', receipts=recs, money=money, q=q)

@app.route('/pending')
def pending():
    rs={r['UnitNo']:r for r in residents()}; dues=[d for d in gs.get_dues() if d['Status']=='Unpaid']
    grouped={}
    for d in dues:
        g=grouped.setdefault(d['UnitNo'],{'owner':rs.get(d['UnitNo'],{}).get('OwnerName',''),'months':[],'total':0})
        g['months'].append(d['Month']); g['total']+=float(d['Amount'])
    return render_template('pending.html', grouped=grouped, money=money)

@app.route("/google-test")
def google_test():
    import json
    import os
    import gspread
    from google.oauth2.service_account import Credentials

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=scope
    )

    client = gspread.authorize(creds)
    
    sheet = client.open(
        os.environ["GOOGLE_SHEET_NAME"]
    )

    return f"✅ Connected Successfully: {sheet.title}"
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
