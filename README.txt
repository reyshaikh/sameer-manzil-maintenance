BUILDING MAINTENANCE COLLECTION SYSTEM - TEST VERSION

QUICK START
1. Extract the ZIP.
2. Double-click setup.bat once.
3. Double-click run.bat whenever you want to start the system.
4. Open http://127.0.0.1:5000 in your browser.

WHAT IS INCLUDED
- 2 sample units with different monthly maintenance amounts
- New collection form
- Automatic total calculation based on selected months
- Receipt number generation
- PDF receipt generation
- Receipt history/search
- Pending dues view
- Dashboard reporting
- WhatsApp click-to-chat message
- CSV-based local database for immediate testing

IMPORTANT WHATSAPP LIMITATION
The free click-to-chat method opens WhatsApp with a prepared message. Browsers do not automatically attach a local PDF. Download the PDF using the Download PDF button, then attach it in WhatsApp and press Send.

TEST DATA
- Shop-01: Javed Takawale, Rs. 300/month
- Flat-101: Test User, Rs. 500/month

EDIT RESIDENTS
Open: data/residents.csv
Columns: UnitNo, OwnerName, MobileNo, MonthlyAmount, Active
Use a 10-digit Indian mobile number without +91.

GOOGLE SHEETS
This package runs immediately using local CSV files so testing is not blocked by account/API setup. Google Sheets synchronization is intentionally not enabled in this test package because Google requires account authorization/credentials. After the workflow is approved, the local storage module can be replaced with a Google Sheets connector while keeping the same screens.

MOBILE TESTING ON SAME WI-FI
The command window displays a Network URL such as http://192.168.x.x:5000. Open that URL on an Android or iPhone connected to the same Wi-Fi. Windows Firewall may ask for permission; allow Private networks.
