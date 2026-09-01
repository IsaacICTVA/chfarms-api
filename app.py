from flask import Flask, jsonify, request, send_file, make_response
from flask_cors import CORS
import json, os, datetime, hashlib, uuid, io
from collections import defaultdict

app = Flask(__name__)
CORS(app, origins="*")

# ── USERS ──────────────────────────────────────────────────────────────────────
USERS = {
    "iyanu":  {"pin": hashlib.sha256("1234".encode()).hexdigest(), "role":"admin",      "name":"Iyanu"},
    "john":   {"pin": hashlib.sha256("2001".encode()).hexdigest(), "role":"counter",    "name":"John"},
    "taiwo":  {"pin": hashlib.sha256("3001".encode()).hexdigest(), "role":"egg_feed",   "name":"Taiwo"},
    "nana":   {"pin": hashlib.sha256("4001".encode()).hexdigest(), "role":"processing", "name":"Nana"},
    "sunday": {"pin": hashlib.sha256("5001".encode()).hexdigest(), "role":"layer",      "name":"Sunday"},
}
SESSIONS = {}

# ── PRICE MASTER ───────────────────────────────────────────────────────────────
FEED_PRICES = {
    "510": {"name":"Broiler Super Starter", "price":19800, "phase":"Day 1–10"},
    "511": {"name":"Broiler Grower",         "price":19600, "phase":"Day 11–21"},
    "512": {"name":"Broiler Finisher",       "price":19500, "phase":"Day 22–35"},
    "324": {"name":"Layer Mash",             "price":15000, "phase":"Layers"},
    "323": {"name":"Layer Concentrate",      "price":15000, "phase":"Layers"},
}
VACCINE_PRICES = {
    "VITRANOR": {"price":10000},
    "LASOTA":   {"price":3500},
    "GUMBORO":  {"price":4800},
    "DD FORCE": {"price":13000},
}
EGG_PRICES = {"medium":5100, "pullet":3800}
DOC_PRICE  = 1740

# ── BATCH MASTER ───────────────────────────────────────────────────────────────
BATCHES = {
    "19a":{"arrival":"09/07/2026","opening":1017,"supplier":"Agrited",
           "feed_code":"512","feed_name":"Broiler Finisher","rearing_days":35},
    "19b":{"arrival":"16/07/2026","opening":1526,"supplier":"Agrited",
           "feed_code":"512","feed_name":"Broiler Finisher","rearing_days":35},
    "20a":{"arrival":"24/08/2026","opening":1020,"supplier":"Agrited",
           "feed_code":"510","feed_name":"Broiler Super Starter","rearing_days":35},
}

# ── PROCESSING EVENTS ──────────────────────────────────────────────────────────
PROCESSING_EVENTS = [
    {"batch":"17","date":"20/07/2026","birds":414,"note":"414 birds processed from Batch 17"},
    {"batch":"18","date":"25/08/2026","birds":184,"note":"184 birds processed from Batch 18"},
]

# ── FEED STOCK (after 25/08/2026 Hephzibah delivery) ─────────────────────────
FEED_STOCK = {
    "510":{"bags":10,"deliveries":[{"date":"25/08/2026","bags":10,"supplier":"Hephzibah Feeds","ref":"C&H.BR/LAY-019","unit_price":19800}]},
    "511":{"bags":0,"deliveries":[]},
    "512":{"bags":40,"deliveries":[{"date":"25/08/2026","bags":40,"supplier":"Hephzibah Feeds","ref":"C&H.BR/LAY-018","unit_price":19500}]},
    "324":{"bags":118,"deliveries":[{"date":"25/08/2026","bags":118,"supplier":"Hephzibah Feeds","ref":"C&H.BR/LAY-017","unit_price":15000}]},
    "323":{"bags":0,"deliveries":[]},
    "205":{"bags":4,"deliveries":[]},
}

# ── DAILY LOG (parsed from field notes) ───────────────────────────────────────
DAILY_LOG = [
    {"date":"09/07/2026","batch":"19a","mort":0,"feed":0.5},
    {"date":"10/07/2026","batch":"19a","mort":0,"feed":0.5},
    {"date":"10/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"11/07/2026","batch":"19a","mort":0,"feed":1.5},
    {"date":"11/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"12/07/2026","batch":"19a","mort":0,"feed":1.5},
    {"date":"12/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"13/07/2026","batch":"19a","mort":1,"feed":1.5},
    {"date":"13/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"14/07/2026","batch":"19a","mort":0,"feed":2.0},
    {"date":"14/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"15/07/2026","batch":"19a","mort":1,"feed":2.0},
    {"date":"15/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"16/07/2026","batch":"19a","mort":0,"feed":4.0},
    {"date":"16/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"16/07/2026","batch":"20a","mort":2,"feed":0.5},
    {"date":"17/07/2026","batch":"19a","mort":1,"feed":1.5},
    {"date":"17/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"18/07/2026","batch":"19a","mort":0,"feed":1.5},
    {"date":"18/07/2026","batch":"19b","mort":0,"feed":0.5},
    {"date":"20/07/2026","batch":"19a","mort":0,"feed":2.0},
    {"date":"20/07/2026","batch":"19b","mort":1,"feed":1.0},
    {"date":"21/07/2026","batch":"19a","mort":1,"feed":2.0},
    {"date":"21/07/2026","batch":"19b","mort":0,"feed":1.0},
    {"date":"22/07/2026","batch":"19a","mort":1,"feed":2.5},
    {"date":"22/07/2026","batch":"19b","mort":1,"feed":1.5},
    {"date":"04/08/2026","batch":"19a","mort":3,"feed":4.0},
    {"date":"04/08/2026","batch":"19b","mort":2,"feed":6.0},
    {"date":"08/08/2026","batch":"19a","mort":0,"feed":5.0},
    {"date":"08/08/2026","batch":"19b","mort":4,"feed":5.0},
    {"date":"09/08/2026","batch":"19a","mort":0,"feed":3.0},
    {"date":"09/08/2026","batch":"19b","mort":0,"feed":4.0},
    {"date":"10/08/2026","batch":"19a","mort":1,"feed":4.0},
    {"date":"10/08/2026","batch":"19b","mort":3,"feed":5.0},
    {"date":"11/08/2026","batch":"19a","mort":0,"feed":5.0},
    {"date":"11/08/2026","batch":"19b","mort":7,"feed":5.0},
    {"date":"12/08/2026","batch":"19a","mort":0,"feed":3.0},
    {"date":"12/08/2026","batch":"19b","mort":28,"feed":3.0},
    {"date":"13/08/2026","batch":"19a","mort":1,"feed":5.0},
    {"date":"13/08/2026","batch":"19b","mort":9,"feed":6.0},
    {"date":"14/08/2026","batch":"19a","mort":0,"feed":5.0},
    {"date":"14/08/2026","batch":"19b","mort":4,"feed":4.0},
    {"date":"15/08/2026","batch":"19a","mort":0,"feed":4.0},
    {"date":"15/08/2026","batch":"19b","mort":4,"feed":4.0},
    {"date":"16/08/2026","batch":"19a","mort":0,"feed":3.0},
    {"date":"16/08/2026","batch":"19b","mort":4,"feed":3.0},
    {"date":"17/08/2026","batch":"19a","mort":0,"feed":1.5},
    {"date":"17/08/2026","batch":"19b","mort":2,"feed":1.5},
    {"date":"18/08/2026","batch":"19a","mort":0,"feed":2.0},
    {"date":"18/08/2026","batch":"19b","mort":6,"feed":2.0},
    {"date":"19/08/2026","batch":"19a","mort":0,"feed":5.0},
    {"date":"19/08/2026","batch":"19b","mort":6,"feed":6.0},
    {"date":"20/08/2026","batch":"19a","mort":2,"feed":5.0},
    {"date":"20/08/2026","batch":"19b","mort":4,"feed":3.0},
    {"date":"21/08/2026","batch":"19a","mort":2,"feed":5.0},
    {"date":"21/08/2026","batch":"19b","mort":2,"feed":6.0},
    {"date":"22/08/2026","batch":"19a","mort":1,"feed":5.0},
    {"date":"22/08/2026","batch":"19b","mort":2,"feed":5.0},
    {"date":"23/08/2026","batch":"19a","mort":1,"feed":3.0},
    {"date":"23/08/2026","batch":"19b","mort":12,"feed":3.0},
    {"date":"24/08/2026","batch":"19a","mort":3,"feed":3.0},
    {"date":"24/08/2026","batch":"19b","mort":17,"feed":2.0},
    {"date":"24/08/2026","batch":"20a","mort":0,"feed":0.0},
]

QUOTES = []
OFFLINE_QUEUE = []

# ── HELPERS ────────────────────────────────────────────────────────────────────
def parse_date(s):
    for fmt in ("%d/%m/%Y","%Y-%m-%d"):
        try: return datetime.datetime.strptime(s,fmt).date()
        except: pass
    return None

def batch_stats(ref_date=None):
    today = ref_date or datetime.date.today()
    cum_mort = defaultdict(float)
    cum_feed = defaultdict(float)
    for r in DAILY_LOG:
        if r["batch"] in BATCHES:
            cum_mort[r["batch"]] += r["mort"]
            cum_feed[r["batch"]] += r["feed"]
    result = {}
    for bk,bv in BATCHES.items():
        arr  = parse_date(bv["arrival"])
        day  = (today - arr).days + 1 if arr else 0
        proc = arr + datetime.timedelta(days=35) if arr else None
        dtop = (proc - today).days if proc else 0
        opening = bv["opening"]
        mort    = int(cum_mort[bk])
        live    = max(0, opening - mort)
        mort_pct= round(mort/opening*100,2) if opening else 0
        feed_bags = round(cum_feed[bk],1)
        fp = FEED_PRICES[bv["feed_code"]]["price"]
        feed_cost = round(feed_bags * fp)
        doc_cost  = opening * DOC_PRICE
        total_cost= doc_cost + feed_cost
        unit_cost = round(total_cost/live,2) if live else 0
        overdue   = day > 35
        if overdue and dtop < 0:
            status = f"OVERDUE by {abs(dtop)}d — Process Immediately"
        elif dtop <= 5 and dtop >= 0:
            status = f"Due in {dtop}d — Prepare for processing"
        else:
            status = f"Day {day}/35 · {dtop}d to processing"
        result[bk] = {
            "batch":bk,"arrival":bv["arrival"],"opening":opening,
            "supplier":bv["supplier"],"feed_code":bv["feed_code"],
            "feed_name":bv["feed_name"],"day":day,
            "processing_date":proc.strftime("%d/%m/%Y") if proc else "—",
            "days_to_processing":dtop,"overdue":overdue,"status":status,
            "cumulative_mortality":mort,"mortality_pct":mort_pct,
            "live_birds":live,"feed_bags_used":feed_bags,"feed_cost":feed_cost,
            "doc_cost":doc_cost,"total_cost_to_date":total_cost,
            "unit_cost_per_bird":unit_cost,
            "alert":mort_pct > 5.0 or overdue,
            "feed_price_per_bag":fp,
        }
    return result

def auth(req):
    t = req.headers.get("Authorization","").replace("Bearer ","")
    return SESSIONS.get(t)

def make_qnum():
    today = datetime.date.today()
    return f"CHF-QT-{today.strftime('%d%m%y')}-{len(QUOTES)+1:03d}"

# ── AUTH ───────────────────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    d = request.json or {}
    u = d.get("username","").lower().strip()
    p = d.get("pin","").strip()
    user = USERS.get(u)
    if not user: return jsonify({"ok":False,"msg":"User not found"}),401
    if user["pin"] != hashlib.sha256(p.encode()).hexdigest():
        return jsonify({"ok":False,"msg":"Incorrect PIN"}),401
    token = str(uuid.uuid4())
    SESSIONS[token] = {"username":u,"role":user["role"],"name":user["name"]}
    return jsonify({"ok":True,"token":token,"role":user["role"],"name":user["name"]})

@app.route("/api/logout",methods=["POST"])
def logout():
    t = request.headers.get("Authorization","").replace("Bearer ","")
    SESSIONS.pop(t,None)
    return jsonify({"ok":True})

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@app.route("/api/dashboard/summary")
def dashboard_summary():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    stats = batch_stats()
    total_live = sum(v["live_birds"] for v in stats.values())
    total_mort = sum(v["cumulative_mortality"] for v in stats.values())
    alerts = [v for v in stats.values() if v["alert"]]
    return jsonify({"ok":True,
        "total_live_birds":total_live,"total_mortality":total_mort,
        "active_batches":len(stats),"processing_revenue":42544929,"egg_revenue":36103665,
        "layer_birds":9239,"pending_quotes":len([q for q in QUOTES if q["status"]=="PROJECTION QUOTE"]),
        "confirmed_quotes":len([q for q in QUOTES if q["status"]=="CONFIRMED"]),
        "offline_queue":len(OFFLINE_QUEUE),"batch_stats":stats,
        "alerts":[{"batch":a["batch"],"msg":a["status"],"mort_pct":a["mortality_pct"]} for a in alerts],
        "processing_events":PROCESSING_EVENTS,
    })

# ── BATCHES ────────────────────────────────────────────────────────────────────
@app.route("/api/batches")
def get_batches():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    return jsonify({"ok":True,"batches":batch_stats(),
        "processing_events":PROCESSING_EVENTS,
        "feed_prices":FEED_PRICES,"vaccine_prices":VACCINE_PRICES})

# ── DAILY LOG ─────────────────────────────────────────────────────────────────
@app.route("/api/daily_log")
def get_daily_log():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    bf = request.args.get("batch")
    running = defaultdict(lambda:{"mort":0.0,"feed":0.0})
    enriched = []
    for r in sorted(DAILY_LOG, key=lambda x:(x["date"],x["batch"])):
        if bf and r["batch"]!=bf: continue
        running[r["batch"]]["mort"] += r["mort"]
        running[r["batch"]]["feed"] += r["feed"]
        b = BATCHES.get(r["batch"],{})
        opening = b.get("opening",0)
        live = max(0, opening - running[r["batch"]]["mort"])
        enriched.append({**r,
            "cumulative_mort":running[r["batch"]]["mort"],
            "cumulative_feed":round(running[r["batch"]]["feed"],1),
            "live_count":live,
            "mort_pct":round(running[r["batch"]]["mort"]/opening*100,2) if opening else 0,
        })
    return jsonify({"ok":True,"log":enriched})

@app.route("/api/daily_log",methods=["POST"])
def add_daily_log():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    d = request.json or {}
    entry = {
        "date":d.get("date",datetime.date.today().strftime("%d/%m/%Y")),
        "batch":d.get("batch"),"mort":float(d.get("mort",0)),
        "feed":float(d.get("feed",0)),"notes":d.get("notes",""),
        "logged_by":sess["name"],
    }
    DAILY_LOG.append(entry)
    OFFLINE_QUEUE.append({"action":"append_row","sheet_tab":"03_Broiler Live Log",
        "data":entry,"ts":datetime.datetime.now().isoformat()})
    return jsonify({"ok":True,"entry":entry,"queued":len(OFFLINE_QUEUE)})

# ── FEED STOCK ────────────────────────────────────────────────────────────────
@app.route("/api/feed_stock")
def get_feed_stock():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    enriched = {}
    for code,fs in FEED_STOCK.items():
        fp = FEED_PRICES.get(code,{})
        bags = fs["bags"]
        price = fp.get("price",0)
        status = "ZERO" if bags==0 else ("Low" if bags<20 else "OK")
        enriched[code] = {**fs,"price":price,"name":fp.get("name","?"),
            "phase":fp.get("phase","?"),"value":bags*price,"status":status}
    stats = batch_stats()
    needs = {}
    for bk,bv in stats.items():
        days_left = max(0,bv["days_to_processing"])
        fc = bv["feed_code"]
        needs[fc] = needs.get(fc,0) + round(days_left * 5)
    return jsonify({"ok":True,"feed_stock":enriched,"projected_needs":needs,
        "feed_prices":FEED_PRICES,"deliveries":[
            {"ref":"C&H.BR/LAY-017","date":"25/08/2026","supplier":"Hephzibah Feeds",
             "type":"Layer Mash","code":"324","bags":118,"unit_price":15000,"total":1770000},
            {"ref":"C&H.BR/LAY-018","date":"25/08/2026","supplier":"Hephzibah Feeds",
             "type":"Broiler Finisher","code":"512","bags":40,"unit_price":19500,"total":780000},
            {"ref":"C&H.BR/LAY-019","date":"25/08/2026","supplier":"Hephzibah Feeds",
             "type":"Broiler Super Starter","code":"510","bags":10,"unit_price":19800,"total":198000},
        ]})

@app.route("/api/feed_stock",methods=["POST"])
def update_feed_stock():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    d = request.json or {}
    code = d.get("code")
    bags = int(d.get("bags",0))
    if code in FEED_STOCK:
        FEED_STOCK[code]["bags"] += bags
        OFFLINE_QUEUE.append({"action":"feed_delivery","data":d,"ts":datetime.datetime.now().isoformat()})
    return jsonify({"ok":True,"new_total":FEED_STOCK.get(code,{}).get("bags",0)})

# ── EGGS ──────────────────────────────────────────────────────────────────────
@app.route("/api/egg_stock")
def get_egg_stock():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    return jsonify({"ok":True,"medium_closing":38,"pullet_closing":40,
        "medium_price":EGG_PRICES["medium"],"pullet_price":EGG_PRICES["pullet"],
        "total_harvested":5970,"total_sold":6910,"total_revenue":36103665,
        "last_date":"24/08/2026","layer_birds":9239})

# ── QUOTE ─────────────────────────────────────────────────────────────────────
@app.route("/api/quote",methods=["POST"])
def create_quote():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    d = request.json or {}
    product    = d.get("product","Broiler Meat")
    qty        = float(d.get("quantity",0))
    unit_price = float(d.get("unit_price",0))
    customer   = d.get("customer_name","")
    phone      = d.get("phone","")
    delivery   = d.get("delivery_date","")
    terms      = d.get("payment_terms","Cash on delivery")
    notes      = d.get("notes","")
    stats = batch_stats()
    due_batches = sorted([(bk,bv) for bk,bv in stats.items() if bv["days_to_processing"]>=0],
                          key=lambda x:x[1]["days_to_processing"])
    next_proc = due_batches[0] if due_batches else None
    is_egg = "Egg" in product
    avail_now = is_egg or (next_proc and next_proc[1]["days_to_processing"]<=7)
    eta = "In stock" if is_egg else (next_proc[1]["processing_date"] if next_proc else "TBC")
    total_val = round(qty * unit_price, 2)
    qnum = make_qnum()
    quote = {
        "quote_number":qnum,"customer_name":customer,"phone":phone,"product":product,
        "quantity":qty,"unit_price":unit_price,"total_value":total_val,
        "delivery_date":delivery,"payment_terms":terms,"notes":notes,
        "quote_date":datetime.date.today().strftime("%d/%m/%Y"),
        "status":"CONFIRMED" if avail_now else "PROJECTION QUOTE",
        "availability_eta":eta,"is_projection":not avail_now,
        "valid_days":7,"agent":sess["name"],
    }
    QUOTES.append(quote)
    OFFLINE_QUEUE.append({"action":"append_row","sheet_tab":"07_Customer_Order_Quote",
        "data":quote,"ts":datetime.datetime.now().isoformat()})
    return jsonify({"ok":True,"quote":quote,"queued":len(OFFLINE_QUEUE)})

@app.route("/api/quotes")
def list_quotes():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    return jsonify({"ok":True,"quotes":QUOTES})

# ── PDF GENERATION ─────────────────────────────────────────────────────────────
@app.route("/api/quote/<qnum>/pdf")
def quote_pdf(qnum):
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    q = next((x for x in QUOTES if x["quote_number"]==qnum),None)
    if not q: return jsonify({"ok":False,"msg":"Quote not found"}),404
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer,HRFlowable
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf,pagesize=A4,
              topMargin=1.5*cm,bottomMargin=2*cm,leftMargin=2*cm,rightMargin=2*cm)
        G  = colors.HexColor("#1A5C2E")
        G2 = colors.HexColor("#D6EDD9")
        A  = colors.HexColor("#D97706")
        A2 = colors.HexColor("#FEF3C7")
        GR = colors.HexColor("#6B7280")
        elems=[]
        def P(txt,**kw): return Paragraph(txt,ParagraphStyle("s",fontName="Helvetica",**kw))
        def B(txt,**kw): return Paragraph(txt,ParagraphStyle("b",fontName="Helvetica-Bold",**kw))
        # Header band
        hdr=Table([[B("CHAPTERS & HEIGHTS FARMS LIMITED",fontSize=15,textColor=colors.white),
                    B(f"QUOTE\n{q['quote_number']}",fontSize=11,textColor=colors.white,alignment=2)]],
                  colWidths=[13*cm,6*cm])
        hdr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),G),("PADDING",(0,0),(-1,-1),12),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        elems+=[hdr,Spacer(1,.3*cm)]
        elems.append(P("Farm Recovery Program · Procurement to Revenue System",fontSize=9,textColor=GR))
        elems+=[Spacer(1,.5*cm)]
        # Meta
        meta=[
            [B("Quote Date:",fontSize=9),P(q['quote_date'],fontSize=9),
             B("Valid Until:",fontSize=9),P(q.get('valid_until',q['quote_date']),fontSize=9)],
            [B("Customer:",fontSize=9),P(q['customer_name'],fontSize=9),
             B("Phone:",fontSize=9),P(q['phone'],fontSize=9)],
            [B("Agent:",fontSize=9),P(q['agent'],fontSize=9),
             B("Payment:",fontSize=9),P(q['payment_terms'],fontSize=9)],
            [B("Status:",fontSize=9),
             B(q['status'],fontSize=9,textColor=G if not q['is_projection'] else A),
             B("Delivery:",fontSize=9),P(q['delivery_date'],fontSize=9)],
        ]
        mt=Table(meta,colWidths=[3.5*cm,6.5*cm,3*cm,6*cm])
        mt.setStyle(TableStyle([("FONTSIZE",(0,0),(-1,-1),9),
            ("GRID",(0,0),(-1,-1),.3,colors.HexColor("#E5E7EB")),
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F9FAFB")),
            ("PADDING",(0,0),(-1,-1),6)]))
        elems+=[mt,Spacer(1,.5*cm)]
        # Line items
        elems.append(B("QUOTE DETAILS",fontSize=10,textColor=G))
        elems.append(Spacer(1,.2*cm))
        unit="kg" if "Meat" in q['product'] or "Bird" in q['product'] else "crates"
        items=[["#","Item Description","Quantity","Unit Price (₦)","Total (₦)"]]
        items.append(["1",q['product'],f"{q['quantity']:,.0f} {unit}",
                      f"₦{q['unit_price']:,.0f}",f"₦{q['total_value']:,.0f}"])
        it=Table(items,colWidths=[.8*cm,9*cm,3*cm,3*cm,3.2*cm])
        it.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),G),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("GRID",(0,0),(-1,-1),.3,colors.HexColor("#D1D5DB")),
            ("PADDING",(0,0),(-1,-1),7),
            ("ALIGN",(2,0),(-1,-1),"RIGHT"),
        ]))
        elems+=[it,Spacer(1,.3*cm)]
        # Totals
        tt=Table([["","","","SUBTOTAL (₦):",f"₦{q['total_value']:,.0f}"],
                  ["","","","VAT (0%):",f"₦0"],
                  ["","","","GRAND TOTAL (₦):",f"₦{q['total_value']:,.0f}"]],
                 colWidths=[.8*cm,9*cm,3*cm,3*cm,3.2*cm])
        tt.setStyle(TableStyle([
            ("FONTNAME",(3,0),(3,-1),"Helvetica-Bold"),
            ("FONTNAME",(4,2),(4,2),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),("ALIGN",(3,0),(-1,-1),"RIGHT"),
            ("BACKGROUND",(3,2),(4,2),G2),
            ("LINEABOVE",(3,0),(4,0),.5,GR),
        ]))
        elems+=[tt,Spacer(1,.5*cm)]
        # Availability block
        nc=G2 if not q['is_projection'] else A2
        ntxt=f"✅  CONFIRMED — Stock available for delivery by {q['delivery_date']}." if not q['is_projection'] \
             else f"📅  PROJECTION QUOTE — Expected availability: {q['availability_eta']}. This quote is subject to stock confirmation. Valid for {q['valid_days']} days."
        nb=Table([[P(ntxt,fontSize=9)]],colWidths=[19*cm])
        nb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),nc),
            ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#D1D5DB")),
            ("PADDING",(0,0),(-1,-1),10)]))
        elems+=[nb,Spacer(1,.5*cm)]
        # Terms
        elems+=[HRFlowable(width="100%",thickness=.5,color=colors.HexColor("#D1D5DB")),
                Spacer(1,.3*cm)]
        elems.append(B("Terms & Conditions",fontSize=9,textColor=G))
        elems.append(Spacer(1,.15*cm))
        terms_txt=[
            "1. This quote is valid for 7 days from the date of issue.",
            "2. Prices are subject to change without prior notice after expiry.",
            "3. Payment terms as stated above. Ownership passes on full payment.",
            "4. Projection quotes are subject to flock availability and processing schedule.",
            "5. C&H Farms reserves the right to amend or withdraw this quotation.",
        ]
        for t in terms_txt:
            elems.append(P(t,fontSize=8,textColor=GR))
        elems.append(Spacer(1,.4*cm))
        # Footer
        ft=Table([[P("Chapters & Heights Farms Limited",fontSize=8,textColor=GR),
                   P(f"Generated by: {q['agent']} | {q['quote_date']}",fontSize=8,textColor=GR,alignment=2)]],
                 colWidths=[10*cm,9*cm])
        ft.setStyle(TableStyle([("LINEABOVE",(0,0),(-1,0),.5,colors.HexColor("#D1D5DB")),
            ("PADDING",(0,0),(-1,-1),4)]))
        elems.append(ft)
        doc.build(elems)
        buf.seek(0)
        return send_file(buf,mimetype="application/pdf",as_attachment=True,
                         download_name=f"CHFarms_{qnum}.pdf")
    except Exception as e:
        return jsonify({"ok":False,"msg":str(e)}),500

# ── SYNC ──────────────────────────────────────────────────────────────────────
@app.route("/api/sync/status")
def sync_status():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    return jsonify({"ok":True,"pending_writes":len(OFFLINE_QUEUE),
        "sheet_id":"1ajWKs867tssC1DqY-miGiLG61eNZIKoZCpv5x-18LvY"})

# sync_flush replaced by sync_flush_real below

@app.route("/api/health")
def health():
    return jsonify({"ok":True,"service":"CH Farms API","version":"2.0.0",
        "sheet_id":"1ajWKs867tssC1DqY-miGiLG61eNZIKoZCpv5x-18LvY"})

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)

# ── LIVE SHEET READ ────────────────────────────────────────────────────────────
@app.route("/api/sheet/read")
def sheet_read():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    sheet_id = os.environ.get("GOOGLE_SHEET_ID","1ajWKs867tssC1DqY-miGiLG61eNZIKoZCpv5x-18LvY")
    try:
        from sheets_sync import read_live_log
        records, err = read_live_log(sheet_id)
        if err:
            return jsonify({"ok":False,"msg":err,"sheet_available":False})
        return jsonify({"ok":True,"records":records,"count":len(records)})
    except ImportError:
        return jsonify({"ok":False,"msg":"sheets_sync module not loaded","sheet_available":False})

# ── REAL SYNC FLUSH WITH SHEETS API ───────────────────────────────────────────
@app.route("/api/sync/flush", methods=["POST"])
def sync_flush_real():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    if sess["role"] != "admin": return jsonify({"ok":False,"msg":"Admin only"}),403

    sheet_id = os.environ.get("GOOGLE_SHEET_ID","1ajWKs867tssC1DqY-miGiLG61eNZIKoZCpv5x-18LvY")
    n = len(OFFLINE_QUEUE)

    # Try live Sheets write-back
    try:
        from sheets_sync import flush_queue
        flushed, errors = flush_queue(list(OFFLINE_QUEUE), sheet_id)
        OFFLINE_QUEUE.clear()
        return jsonify({
            "ok":True,"flushed":flushed,"errors":errors,
            "msg":f"{flushed} of {n} writes sent to Google Sheet",
            "sheet_write_attempted":True,
        })
    except ImportError:
        # Fallback: just clear queue (no live sheet)
        OFFLINE_QUEUE.clear()
        return jsonify({"ok":True,"flushed":n,"errors":[],"msg":f"{n} writes flushed (offline mode)","sheet_write_attempted":False})

# ── EMAIL ALERT (free via SMTP Gmail) ─────────────────────────────────────────
def send_email_alert(subject, body, to_email):
    """Free email alert via Gmail SMTP (requires GMAIL_USER + GMAIL_PASS env vars)."""
    import smtplib
    from email.mime.text import MIMEText
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_PASS")
    if not gmail_user or not gmail_pass:
        return False, "GMAIL_USER or GMAIL_PASS not set"
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"]    = gmail_user
        msg["To"]      = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(gmail_user, gmail_pass)
            s.sendmail(gmail_user, [to_email], msg.as_string())
        return True, "Sent"
    except Exception as e:
        return False, str(e)

@app.route("/api/alert/email", methods=["POST"])
def alert_email():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    d = request.json or {}
    subject = d.get("subject","C&H Farms Alert")
    body    = d.get("body","")
    to      = d.get("to", os.environ.get("ALERT_EMAIL",""))
    if not to: return jsonify({"ok":False,"msg":"No recipient email configured (set ALERT_EMAIL env var)"})
    ok, msg = send_email_alert(subject, body, to)
    return jsonify({"ok":ok,"msg":msg})

# ── WHATSAPP ALERT (free via Twilio sandbox or CallMeBot) ────────────────────
@app.route("/api/alert/whatsapp", methods=["POST"])
def alert_whatsapp():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    d = request.json or {}
    message = d.get("message","")
    phone   = d.get("phone", os.environ.get("WHATSAPP_PHONE",""))

    # Try CallMeBot (free WhatsApp API — no cost, just one-time setup)
    apikey  = os.environ.get("CALLMEBOT_KEY","")
    if apikey and phone:
        try:
            import urllib.request, urllib.parse
            url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={urllib.parse.quote(message)}&apikey={apikey}"
            urllib.request.urlopen(url, timeout=10)
            return jsonify({"ok":True,"msg":"WhatsApp alert sent via CallMeBot","provider":"callmebot"})
        except Exception as e:
            return jsonify({"ok":False,"msg":str(e)})

    # Fallback: Twilio WhatsApp sandbox (free for dev)
    twilio_sid  = os.environ.get("TWILIO_SID","")
    twilio_auth = os.environ.get("TWILIO_AUTH","")
    if twilio_sid and twilio_auth and phone:
        try:
            import urllib.request, urllib.parse, base64
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            data = urllib.parse.urlencode({
                "From": "whatsapp:+14155238886",
                "To":   f"whatsapp:{phone}",
                "Body": message
            }).encode()
            req = urllib.request.Request(url, data)
            creds = base64.b64encode(f"{twilio_sid}:{twilio_auth}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
            urllib.request.urlopen(req, timeout=10)
            return jsonify({"ok":True,"msg":"WhatsApp sent via Twilio","provider":"twilio"})
        except Exception as e:
            return jsonify({"ok":False,"msg":str(e)})

    return jsonify({"ok":False,"msg":"No WhatsApp provider configured. Set CALLMEBOT_KEY+WHATSAPP_PHONE or TWILIO_SID+TWILIO_AUTH+WHATSAPP_PHONE"})

# ── MORTALITY ALERT TRIGGER ───────────────────────────────────────────────────
@app.route("/api/alert/check_mortality", methods=["POST"])
def check_mortality_alert():
    """Auto-send alert if any batch exceeds 5% mortality or is overdue."""
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    stats = batch_stats()
    alerts_sent = []
    for bk, bv in stats.items():
        if bv["mortality_pct"] > 5.0 or bv["overdue"]:
            subject = f"⚠ C&H Farms Alert — Batch {bk}"
            body = (
                f"ALERT: Batch {bk}\n"
                f"Status: {bv['status']}\n"
                f"Mortality: {bv['cumulative_mortality']} birds ({bv['mortality_pct']}%)\n"
                f"Live birds: {bv['live_birds']}\n"
                f"Processing date: {bv['processing_date']}\n"
                f"Days to processing: {bv['days_to_processing']}\n"
                f"Date: {datetime.date.today().strftime('%d/%m/%Y')}\n"
                f"Action required: Immediate review."
            )
            email = os.environ.get("ALERT_EMAIL","")
            if email:
                ok, msg = send_email_alert(subject, body, email)
                alerts_sent.append({"batch":bk,"method":"email","ok":ok,"msg":msg})
    return jsonify({"ok":True,"alerts_sent":alerts_sent,"checked":len(stats)})

# ── PROCESSING LOG ────────────────────────────────────────────────────────────
@app.route("/api/processing", methods=["GET"])
def get_processing():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    return jsonify({"ok":True,"events":PROCESSING_EVENTS,
        "summary":{"b17_birds":414,"b18_birds":184,"total_processed":598}})

@app.route("/api/processing", methods=["POST"])
def add_processing():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    if sess["role"] not in ("admin","processing"):
        return jsonify({"ok":False,"msg":"Processing role required"}),403
    d = request.json or {}
    event = {"batch":d.get("batch"),"date":d.get("date"),"birds":int(d.get("birds",0)),
             "weight_kg":float(d.get("weight_kg",0)),"price_per_kg":float(d.get("price_per_kg",0)),
             "revenue":float(d.get("weight_kg",0))*float(d.get("price_per_kg",0)),
             "note":d.get("note",""),"logged_by":sess["name"]}
    PROCESSING_EVENTS.append(event)
    OFFLINE_QUEUE.append({"action":"append_row","sheet_tab":"02_Processing Log",
        "data":event,"ts":datetime.datetime.now().isoformat()})
    return jsonify({"ok":True,"event":event,"queued":len(OFFLINE_QUEUE)})

# ── VACCINE LOG ────────────────────────────────────────────────────────────────
VACCINE_LOG = []
@app.route("/api/vaccines", methods=["GET"])
def get_vaccines():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    schedule = [
        {"batch":"19a","day":7, "vaccine":"LASOTA",   "price":3500,  "status":"Done"},
        {"batch":"19a","day":14,"vaccine":"GUMBORO",  "price":4800,  "status":"Done"},
        {"batch":"19a","day":21,"vaccine":"VITRANOR", "price":10000, "status":"Done"},
        {"batch":"19b","day":7, "vaccine":"LASOTA",   "price":3500,  "status":"Done"},
        {"batch":"19b","day":14,"vaccine":"GUMBORO",  "price":4800,  "status":"Done"},
        {"batch":"19b","day":21,"vaccine":"DD FORCE", "price":13000, "status":"Done"},
        {"batch":"20a","day":7, "vaccine":"LASOTA",   "price":3500,  "status":"Scheduled"},
        {"batch":"20a","day":14,"vaccine":"GUMBORO",  "price":4800,  "status":"Scheduled"},
        {"batch":"20a","day":21,"vaccine":"VITRANOR", "price":10000, "status":"Scheduled"},
        {"batch":"20a","day":28,"vaccine":"DD FORCE", "price":13000, "status":"Scheduled"},
    ]
    return jsonify({"ok":True,"schedule":schedule,"vaccine_prices":VACCINE_PRICES,
        "user_log":VACCINE_LOG})

@app.route("/api/vaccines", methods=["POST"])
def log_vaccine():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    d = request.json or {}
    entry = {**d,"logged_by":sess["name"],"ts":datetime.datetime.now().isoformat()}
    VACCINE_LOG.append(entry)
    OFFLINE_QUEUE.append({"action":"append_row","sheet_tab":"04_Vaccine_Drug_Log",
        "data":entry,"ts":entry["ts"]})
    return jsonify({"ok":True,"entry":entry,"queued":len(OFFLINE_QUEUE)})
