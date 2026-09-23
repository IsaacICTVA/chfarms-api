from sqlalchemy.exc import SQLAlchemyError
from flask import Flask, jsonify, request, send_file, make_response
from flask_cors import CORS
import json, os, datetime, hashlib, uuid, io
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError
app = Flask(__name__)
CORS(app, origins="*")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required for production."
    )

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# ── USERS ──────────────────────────────────────────────────────────────────────
USERS = {
    "iyanu":  {"pin": hashlib.sha256("1234".encode()).hexdigest(), "role":"admin",      "name":"Iyanu"},
    "john":   {"pin": hashlib.sha256("2001".encode()).hexdigest(), "role":"counter",    "name":"John"},
    "taiwo":  {"pin": hashlib.sha256("3001".encode()).hexdigest(), "role":"egg_feed",   "name":"Taiwo"},
    "nana":   {"pin": hashlib.sha256("4001".encode()).hexdigest(), "role":"processing", "name":"Nana"},
    "sunday": {"pin": hashlib.sha256("5001".encode()).hexdigest(), "role":"layer",      "name":"Sunday"},
}
SESSIONS = {}

# Permission checks are enforced here as well as in the dashboard UI.  Hiding a
# menu item is only a convenience; it must never be the access-control layer.
ROLE_PERMISSIONS = {
    "admin": {"*"},
    "counter": {"daily_log", "quotes", "vaccines"},
    "egg_feed": {"feed_stock", "egg_stock"},
    "processing": {"processing"},
    "layer": {"layers", "egg_stock"},
}

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
EGG_LOG = []

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

def has_permission(sess, permission):
    return bool(sess) and ("*" in ROLE_PERMISSIONS.get(sess["role"], set())
                           or permission in ROLE_PERMISSIONS.get(sess["role"], set()))

def require_permission(sess, permission):
    if not sess:
        return jsonify({"ok":False,"msg":"Unauthorized"}), 401
    if not has_permission(sess, permission):
        return jsonify({"ok":False,"msg":"Your role is not permitted to perform this action."}), 403
    return None

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
        "as_of":datetime.datetime.now(datetime.timezone.utc).isoformat(),
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
    denied = require_permission(sess, "daily_log")
    if denied: return denied
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
    denied = require_permission(sess, "feed_stock")
    if denied: return denied
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

@app.route("/api/egg_stock", methods=["POST"])
def add_egg_stock():
    sess = auth(request)
    denied = require_permission(sess, "egg_stock")
    if denied: return denied
    d = request.json or {}
    entry = {
        "date": d.get("date", datetime.date.today().strftime("%d/%m/%Y")),
        "pullet_collected": int(d.get("pullet_collected", 0)),
        "pullet_sold": int(d.get("pullet_sold", 0)),
        "pullet_closing": int(d.get("pullet_closing", 0)),
        "medium_collected": int(d.get("medium_collected", 0)),
        "medium_sold": int(d.get("medium_sold", 0)),
        "medium_closing": int(d.get("medium_closing", 0)),
        "daily_revenue": float(d.get("daily_revenue", 0)),
        "logged_by": sess["name"],
    }
    EGG_LOG.append(entry)
    OFFLINE_QUEUE.append({"action":"append_row","sheet_tab":"05_Egg_Stock_Log",
        "data":entry,"ts":datetime.datetime.now().isoformat()})
    return jsonify({"ok":True,"entry":entry,"queued":len(OFFLINE_QUEUE)})

# ── QUOTE ─────────────────────────────────────────────────────────────────────
@app.route("/api/quote",methods=["POST"])
def create_quote():
    sess = auth(request)
    denied = require_permission(sess, "quotes")
    if denied: return denied
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
    denied = require_permission(sess, "quotes")
    if denied: return denied
    return jsonify({"ok":True,"quotes":QUOTES})

# ── PDF GENERATION ─────────────────────────────────────────────────────────────
@app.route("/api/quote/<qnum>/pdf")
def quote_pdf(qnum):
    sess = auth(request)
    denied = require_permission(sess, "quotes")
    if denied: return denied
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
        "sheet_configured":bool(os.environ.get("GOOGLE_SHEET_ID"))})

# sync_flush replaced by sync_flush_real below

@app.route("/api/health")
def health():
    try:
        from sqlalchemy import text

        db.session.execute(text("SELECT 1"))

        database_url = app.config[
            "SQLALCHEMY_DATABASE_URI"
        ]

        if database_url.startswith("postgresql"):
            database = "postgresql"
        elif database_url.startswith("sqlite"):
            database = "sqlite"
        else:
            database = "unknown"

        return jsonify({
            "ok": True,
            "service": "CH Farms API",
            "version": "2.1.0",
            "database": database,
            "sheet_configured": bool(
                os.environ.get("GOOGLE_SHEET_ID")
            )
        })

    except Exception:
        app.logger.exception(
            "Health check failed"
        )

        return jsonify({
            "ok": False,
            "service": "CH Farms API",
            "database": "unavailable"
        }), 503
@app.route("/")
def serve_dashboard():
    # Serve the maintained dashboard file.  The previous embedded base64 copy
    # drifted from index.html, making live dashboard fixes invisible on Render.
    return send_file("index.html", mimetype="text/html")

@app.route("/dashboard")
def serve_dashboard_alias():
    from flask import redirect
    return redirect("/", code=301)

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)

# ── GOOGLE SHEETS SYNC ────────────────────────────────────────────────────────
def _sheets_error(message, status=503):
    return jsonify({"ok": False, "msg": message, "sheet_available": False}), status

@app.route("/api/sheet/status")
def sheet_status():
    """Report Google Sheets state without returning any secret values."""
    sess = auth(request)
    denied = require_permission(sess, "sheets")
    if denied: return denied
    try:
        from sheets_sync import get_sheets_service
        import asyncio
        return jsonify({"ok": True, **asyncio.run(get_sheets_service().status())})
    except Exception:
        return jsonify({"ok": True, "configured": False, "available": False,
                        "detail": "Google Sheets is not configured."})

@app.route("/api/sheet/read")
@app.route("/api/sheet/logs")
def sheet_read():
    sess = auth(request)
    denied = require_permission(sess, "sheets")
    if denied: return denied
    try:
        from sheets_sync import DEFAULT_BROILER_TAB, get_sheets_service
        import asyncio
        tab = request.args.get("tab", DEFAULT_BROILER_TAB)
        raw_limit = request.args.get("limit")
        limit = int(raw_limit) if raw_limit else None
        records = asyncio.run(get_sheets_service().read_records(tab, limit))
        return jsonify({"ok":True,"records":records,"count":len(records)})
    except ValueError as exc:
        return jsonify({"ok":False,"msg":str(exc)}),400
    except Exception:
        return _sheets_error("Unable to read Google Sheets live logs.")

# ── REAL SYNC FLUSH WITH SHEETS API ───────────────────────────────────────────
@app.route("/api/sync/flush", methods=["POST"])
def sync_flush_real():
    sess = auth(request)
    denied = require_permission(sess, "sheets")
    if denied: return denied

    queue_snapshot = list(OFFLINE_QUEUE)
    try:
        from sheets_sync import get_sheets_service
        import asyncio
        result = asyncio.run(get_sheets_service().flush(queue_snapshot))
        failed = set(result.failed_indexes)
        # Failed entries remain queued so a later retry cannot lose farm records.
        OFFLINE_QUEUE[:] = [item for index, item in enumerate(queue_snapshot) if index in failed]
        return jsonify({
            "ok":not result.errors,"flushed":result.flushed,"errors":list(result.errors),
            "remaining":len(OFFLINE_QUEUE),
            "msg":f"{result.flushed} writes sent to Google Sheet",
            "sheet_write_attempted":True,
        })
    except Exception:
        return _sheets_error("Unable to flush Google Sheets queue; queued data was retained.")

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
    denied = require_permission(sess, "alerts")
    if denied: return denied
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
    denied = require_permission(sess, "alerts")
    if denied: return denied
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
    denied = require_permission(sess, "alerts")
    if denied: return denied
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
    denied = require_permission(sess, "processing")
    if denied: return denied
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
    denied = require_permission(sess, "vaccines")
    if denied: return denied
    d = request.json or {}
    entry = {**d,"logged_by":sess["name"],"ts":datetime.datetime.now().isoformat()}
    VACCINE_LOG.append(entry)
    OFFLINE_QUEUE.append({"action":"append_row","sheet_tab":"04_Vaccine_Drug_Log",
        "data":entry,"ts":entry["ts"]})
    return jsonify({"ok":True,"entry":entry,"queued":len(OFFLINE_QUEUE)})

# ── LAYER BIRDS LOG ────────────────────────────────────────────────────────────
LAYER_LOG = [
    {"date":"21/07/2026","counter":"Sunday","layer_opening":9239,
     "layer_mortality":0,"layer_closing":9239,"notes":"Split tracking begins"},
    {"date":"22/07/2026","counter":"Sunday","layer_opening":9239,
     "layer_mortality":2,"layer_closing":9237,"notes":""},
    {"date":"23/07/2026","counter":"Sunday","layer_opening":9237,
     "layer_mortality":1,"layer_closing":9236,"notes":""},
    {"date":"24/07/2026","counter":"Sunday","layer_opening":9236,
     "layer_mortality":0,"layer_closing":9236,"notes":""},
]

@app.route("/api/layers", methods=["GET"])
def get_layers():
    sess = auth(request)
    if not sess: return jsonify({"ok":False,"msg":"Unauthorized"}),401
    # Compute current from log
    if LAYER_LOG:
        latest = LAYER_LOG[-1]
        closing = latest["layer_closing"]
        cum_mort = sum(r["layer_mortality"] for r in LAYER_LOG)
    else:
        closing = 9239
        cum_mort = 0
    opening = 9239  # initial flock
    return jsonify({"ok":True,
        "opening_flock":opening,
        "current_live":closing,
        "cumulative_mortality":cum_mort,
        "mortality_pct":round(cum_mort/opening*100,3) if opening else 0,
        "log":LAYER_LOG[-10:],  # last 10 entries
        "egg_prices":{"medium":5100,"pullet":3800},
    })

@app.route("/api/layers", methods=["POST"])
def add_layer_log():
    sess = auth(request)
    denied = require_permission(sess, "layers")
    if denied: return denied
    d = request.json or {}
    # Get last closing as new opening
    if LAYER_LOG:
        opening = LAYER_LOG[-1]["layer_closing"]
    else:
        opening = int(d.get("layer_opening", 9239))
    mort = int(d.get("layer_mortality", 0))
    closing = opening - mort
    entry = {
        "date": d.get("date", datetime.date.today().strftime("%d/%m/%Y")),
        "counter": sess["name"],
        "layer_opening": opening,
        "layer_mortality": mort,
        "layer_closing": closing,
        "notes": d.get("notes",""),
    }
    LAYER_LOG.append(entry)
    OFFLINE_QUEUE.append({"action":"append_row","sheet_tab":"05_Layer_Log",
        "data":entry,"ts":datetime.datetime.now().isoformat()})
    return jsonify({"ok":True,"entry":entry,"current_live":closing,"queued":len(OFFLINE_QUEUE)})

# ── Q3 DURABLE OPERATIONS ─────────────────────────────────────────────────────
def q3_denied(sess, permission):
    return require_permission(sess, permission)

def q3_date(value):
    parsed = parse_date(value)
    if not parsed: raise ValueError("date must use DD/MM/YYYY or YYYY-MM-DD")
    return parsed

def q3_audit(action, entity, actor, reason=""):
    db.session.add(AuditLog(action=action, entity_type=entity.__class__.__name__, entity_id=entity.id, actor=actor, reason=reason))

@app.route("/api/q3/doc-arrivals", methods=["GET", "POST"])
def q3_doc_arrivals():
    sess = auth(request)

    denied = q3_denied(sess, "feed_stock")
    if denied:
        return denied

    # -----------------------------
    # GET: list Batch Arrivals
    # -----------------------------
    if request.method == "GET":
        try:
            rows = (
                BatchArrival.query
                .order_by(BatchArrival.arrival_date.desc())
                .all()
            )

            return jsonify({
                "ok": True,
                "arrivals": [
                    {
                        "id": r.id,
                        "batch_code": r.batch_code,
                        "arrival_date": (
                            r.arrival_date.isoformat()
                            if r.arrival_date
                            else None
                        ),
                        "supplier": r.supplier,
                        "doc_count": r.doc_count,
                        "unit_cost": float(r.unit_cost),
                        "feed_type": r.feed_type,
                        "house": r.house,
                        "status": r.status
                    }
                    for r in rows
                ]
            })

        except SQLAlchemyError:
            app.logger.exception(
                "Q3 Batch Arrival read database error"
            )

            return jsonify({
                "ok": False,
                "error": "database_error",
                "msg": "Batch Arrivals could not be loaded."
            }), 500

    # -----------------------------
    # POST: create Batch Arrival
    # -----------------------------
    d = request.json or {}

    try:
        record = BatchArrival(
            batch_code=str(
                d["batch_code"]
            ).strip().lower(),

            arrival_date=q3_date(
                d["arrival_date"]
            ),

            supplier=str(
                d["supplier"]
            ).strip(),

            doc_count=int(
                d["doc_count"]
            ),

            unit_cost=float(
                d["unit_cost"]
            ),

            feed_type=str(
                d["feed_type"]
            ).strip(),

            house=d.get("house"),

            created_by=sess["name"]
        )

        if record.doc_count <= 0:
            raise ValueError(
                "DOC count must be positive"
            )

        if record.unit_cost < 0:
            raise ValueError(
                "Unit cost cannot be negative"
            )

        db.session.add(record)

        q3_audit(
            "create",
            record,
            sess["name"],
            d.get(
                "reason",
                "New DOC arrival"
            )
        )

        db.session.commit()

        return jsonify({
            "ok": True,
            "id": record.id
        }), 201

    except (KeyError, TypeError, ValueError) as exc:
        db.session.rollback()

        return jsonify({
            "ok": False,
            "msg": str(exc)
        }), 400

    except SQLAlchemyError:
        db.session.rollback()

        app.logger.exception(
            "Q3 Batch Arrival database error"
        )

        return jsonify({
            "ok": False,
            "error": "database_error",
            "msg": "Batch Arrival could not be saved."
        }), 500
@app.route("/api/q3/feed-records", methods=["GET", "POST"])
def q3_feed_records():
    sess = auth(request)

    denied = q3_denied(sess, "feed_stock")
    if denied:
        return denied

    if request.method == "GET":
        try:
            rows = (
                FeedRecord.query
                .order_by(FeedRecord.record_date.desc())
                .all()
            )

            supply = sum(
                float(r.quantity_bags)
                for r in rows
                if r.movement_type == "supply"
            )

            used = sum(
                float(r.quantity_bags)
                for r in rows
                if r.movement_type == "usage"
            )

            return jsonify({
                "ok": True,
                "supply_bags": supply,
                "usage_bags": used,
                "closing_bags": supply - used,
                "records": [
                    {
                        "id": r.id,
                        "date": (
                            r.record_date.isoformat()
                            if r.record_date
                            else None
                        ),
                        "type": r.movement_type,
                        "feed_type": r.feed_type,
                        "bags": float(r.quantity_bags),
                        "batch": r.batch_code,
                        "house": r.house,
                        "supplier": r.supplier,
                        "unit_cost": float(r.unit_cost or 0),
                        "reference": r.reference,
                    }
                    for r in rows
                ],
            })

        except SQLAlchemyError:
            app.logger.exception(
                "Q3 Feed Record read database error"
            )

            return jsonify({
                "ok": False,
                "error": "database_error",
                "msg": "Feed Records could not be loaded.",
            }), 500

    d = request.get_json(silent=True) or {}

    try:
        movement = d.get("movement_type")

        if movement not in {"supply", "usage"}:
            raise ValueError(
                "movement_type must be supply or usage"
            )

        record = FeedRecord(
            record_date=q3_date(d["record_date"]),
            movement_type=movement,
            feed_type=str(d["feed_type"]).strip(),
            quantity_bags=float(d["quantity_bags"]),
            batch_code=d.get("batch_code"),
            house=d.get("house"),
            supplier=d.get("supplier"),
            unit_cost=d.get("unit_cost"),
            reference=d.get("reference"),
            notes=d.get("notes"),
            created_by=sess["name"],
        )

        if record.quantity_bags <= 0:
            raise ValueError(
                "quantity_bags must be positive"
            )

        db.session.add(record)

        q3_audit(
            "create",
            record,
            sess["name"],
            d.get("reason", "Feed record"),
        )

        db.session.commit()

        return jsonify({
            "ok": True,
            "id": record.id,
        }), 201

    except (KeyError, TypeError, ValueError) as exc:
        db.session.rollback()

        return jsonify({
            "ok": False,
            "error": "validation_error",
            "msg": str(exc),
        }), 400

    except SQLAlchemyError:
        db.session.rollback()

        app.logger.exception(
            "Q3 Feed Record database error"
        )

        return jsonify({
            "ok": False,
            "error": "database_error",
            "msg": "Feed Record could not be saved.",
        }), 500


@app.route("/api/q3/processing-sessions", methods=["POST"])
def q3_processing_session():
    sess = auth(request)

    denied = q3_denied(sess, "processing")
    if denied:
        return denied

    d = request.get_json(silent=True) or {}

    try:
        session = ProcessingSession(
            processing_date=q3_date(
                d["processing_date"]
            ),
            source_batch=str(
                d["source_batch"]
            ).strip(),
            birds_received=int(
                d["birds_received"]
            ),
            birds_processed=int(
                d["birds_processed"]
            ),
            birds_rejected=int(
                d.get("birds_rejected", 0)
            ),
            live_weight_kg=float(
                d.get("live_weight_kg", 0)
            ),
            labor_cost=float(
                d.get("labor_cost", 0)
            ),
            transport_cost=float(
                d.get("transport_cost", 0)
            ),
            utilities_cost=float(
                d.get("utilities_cost", 0)
            ),
            packaging_cost=float(
                d.get("packaging_cost", 0)
            ),
            inspection_cost=float(
                d.get("inspection_cost", 0)
            ),
            other_cost=float(
                d.get("other_cost", 0)
            ),
            created_by=sess["name"],
        )

        if (
            session.birds_processed
            + session.birds_rejected
            > session.birds_received
        ):
            raise ValueError(
                "processed and rejected birds cannot exceed birds received"
            )

        items = d.get("items", [])

        if not items:
            raise ValueError(
                "at least one whole, part, or evisceral item is required"
            )

        for item_data in items:
            product = str(
                item_data["product"]
            ).strip()

            category = str(
                item_data["category"]
            ).strip()

            if category not in {
                "whole",
                "part",
                "evisceral",
            }:
                raise ValueError(
                    "item category must be whole, part, or evisceral"
                )

            item = ProcessingItem(
                product=product,
                category=category,
                weight_kg=float(
                    item_data["weight_kg"]
                ),
                pack_count=float(
                    item_data.get("pack_count", 0)
                ),
                unit=item_data.get("unit", "kg"),
                selling_rate=float(
                    item_data["selling_rate"]
                ),
            )

            session.items.append(item)

        db.session.add(session)

        q3_audit(
            "create",
            session,
            sess["name"],
            d.get(
                "reason",
                "Processing session",
            ),
        )

        db.session.commit()

        revenue = sum(
            float(i.sale_value or 0)
            for i in session.items
        )

        return jsonify({
            "ok": True,
            "id": session.id,
            "expense_total": session.expense_total,
            "revenue_total": revenue,
            "margin": (
                revenue
                - float(session.expense_total or 0)
            ),
        }), 201

    except (KeyError, TypeError, ValueError) as exc:
        db.session.rollback()

        return jsonify({
            "ok": False,
            "error": "validation_error",
            "msg": str(exc),
        }), 400

    except SQLAlchemyError:
        db.session.rollback()

        app.logger.exception(
            "Q3 Processing Session database error"
        )

        return jsonify({
            "ok": False,
            "error": "database_error",
            "msg": "Processing Session could not be saved.",
        }), 500
    @app.route("/api/q3/audit-log", methods=["GET"])
def q3_audit_log():

db.session.commit()
        revenue=sum(i.sale_value for i in session.items)
        return jsonify({"ok":True,"id":session.id,"expense_total":session.expense_total,"revenue_total":revenue,"margin":revenue-session.expense_total}), 201
    except SQLAlchemyError:
    db.session.rollback()
    app.logger.exception(
        "Q3 Processing Session database error"
    )
    return jsonify({
        "ok": False,
        "error": "database_error",
        "msg": "Processing Session could not be saved."
    }), 500
@app.route("/api/q3/audit-log", methods=["GET"])
def q3_audit_log():
    sess = auth(request)

    denied = q3_denied(sess, "admin")
    if denied:
        return denied

    try:
        rows = (
            AuditLog.query
            .order_by(AuditLog.created_at.desc())
            .limit(200)
            .all()
        )

        return jsonify({
            "ok": True,
            "audit": [
                {
                    "id": r.id,
                    "action": r.action,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "actor": r.actor,
                    "reason": r.reason,
                    "created_at": (
                        r.created_at.isoformat()
                        if r.created_at
                        else None
                    )
                }
                for r in rows
            ]
        })

    except SQLAlchemyError:
        app.logger.exception(
            "Q3 Audit Log database error"
        )

        return jsonify({
            "ok": False,
            "error": "database_error",
            "msg": "Audit Log could not be loaded."
        }), 500
