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
    rows=[['Sr. No.','PARTICULARS','Amount (₹)']]
    for i,d in enumerate(selected_dues,1): rows.append([str(i), f"Maintenance Charges - {d['Month']}", f"{float(d['Amount']):,.2f}"])
    rows.append(['','TOTAL AMOUNT',f"{float(rec['TotalAmount']):,.2f}"])
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

@app.route('/collection', methods=['GET','POST'])
def collection():
    rs = gs.get_residents()
    dues = gs.get_dues()
    if request.method=='POST':
        unit=request.form['unit']; months=request.form.getlist('months'); mode=request.form['payment_mode']; txn=request.form.get('transaction_id','').strip()
        person=next((r for r in rs if r['UnitNo']==unit),None)
        selected=[d for d in dues if d['UnitNo']==unit and d['Month'] in months and d['Status']=='Unpaid']
        if not person or not selected:
            flash('Select a unit and at least one unpaid month.'); return redirect(url_for('collection'))
        if mode in ('UPI','Bank Transfer','Cheque') and not txn:
            flash('Transaction/Cheque number is required for the selected payment mode.'); return redirect(url_for('collection'))
        no=next_receipt_no(); now=datetime.now(); total=sum(float(d['Amount']) for d in selected)
        rec={'ReceiptNo':no,'ReceiptDate':now.strftime('%d-%b-%Y'),'UnitNo':unit,'OwnerName':person['OwnerName'],'MobileNo':person['MobileNo'],'PeriodFrom':selected[0]['Month'],'PeriodTo':selected[-1]['Month'],'Months':','.join(d['Month'] for d in selected),'TotalAmount':str(total),'PaymentMode':mode,'TransactionID':txn,'PaymentStatus':'Paid','PDFFile':''}
        rec['PDFFile']=generate_pdf(rec,selected)
        gs.save_receipt(rec)

        gs.save_receipt_details(
            no,
            selected
        )
        
        gs.mark_due_paid(
            unit,
            months,
            no,
            now.strftime("%Y-%m-%d")
        )
        return redirect(url_for('receipt_result', receipt_no=no))
    due_map={r['UnitNo']:[d for d in dues if d['UnitNo']==r['UnitNo'] and d['Status']=='Unpaid'] for r in rs}
    return render_template('collection.html', residents=rs, due_map=due_map)

@app.route('/receipt/<receipt_no>')
def receipt_result(receipt_no):
    rec=next((r for r in gs.get_receipts() if r['ReceiptNo']==receipt_no),None)
    if not rec: return 'Receipt not found',404
    mobile='91'+''.join(filter(str.isdigit,rec['MobileNo']))[-10:]
    msg=(f"Dear {rec['OwnerName']},\n\nYour maintenance payment has been received.\n"
         f"Receipt No: {rec['ReceiptNo']}\nAmount: {money(rec['TotalAmount'])}\n"
         f"Period: {rec['PeriodFrom']} to {rec['PeriodTo']}\n\n"
         f"Please attach the downloaded PDF receipt before sending.\n\nRegards,\nSameer Manzil Co-op. Society")
    wa=f"https://wa.me/{mobile}?text={urllib.parse.quote(msg)}"
    return render_template('receipt_result.html', r=rec, wa=wa, money=money)

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
