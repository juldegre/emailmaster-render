# email_core.py — Picsouille Good Vibes + Auto-Reply (Render)
import os, json, base64, re, random
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- Config via variables d’environnement Render ---
LAURE_EMAILS = [e.strip() for e in os.getenv("LAURE_EMAILS","").split(",") if e.strip()]
SEND_SUMMARY_TO = os.getenv("SEND_SUMMARY_TO","")
TARGET_LABEL = os.getenv("TARGET_LABEL","Picsouille")
IMPORTANT_KEYWORDS = [k.strip() for k in os.getenv("IMPORTANT_KEYWORDS",
    "Hugo,Axel,tribunal,pension,CAF,scolarité,collège,lycée,rendez-vous,rdv,urgence,malade,accident,BAFA,virement,paiement,euro,€,scolaire,extrascolaire,extra scolaire"
).split(",") if k.strip()]

GOOD_VIBES = {
    "Hugo":["Mission douceur pour Hugo today 👑","Hugo gère ça comme un pro 💪"],
    "Axel":["Axel prépare un coup de maître 🎯","Axel en mission spéciale 🚀"],
    "tribunal":["Réunion très chic avec des gens en costume ⚖️","Paperasse officielle au menu, easy game 😎"],
    "pension":["Petit geste mensuel en préparation 💌","La logistique financière suit son cours 💼"],
    "paiement":["Le compte fait la danse de la joie 💸","Flux financier sous contrôle ✅"],
    "virement":["Vague de richesse en approche 🌊💰","Fonds en route avec chauffeur privé 🚗💵"],
    "malade":["Journée cocooning sous plaid autorisée 🛌☕","Pause soin et douceur au programme 🌸"],
    "scolaire":["Nouvelles du front éducatif 📚","Mission devoirs & organisation ✏️"],
    "extrascolaire":["Programme extra cool détecté 🎨","Activité bonus qui fait plaisir 🎭"],
    "rdv":["Tu es convié au club VIP des parents 🎓","Rendez-vous noté, on y va zen 🧘"]
}

MONTHS_FR = "(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
DATE_PATS = [rf"\b(\d{{1,2}})\s*/\s*(\d{{1,2}})(?:\s*/\s*(\d{{2,4}}))?\b",
             rf"\b(\d{{1,2}})\s+{MONTHS_FR}(?:\s+(\d{{4}}))?\b"]
TIME_PATS = [r"\b(\d{1,2})[:hH](\d{2})\b", r"\b(\d{1,2})h\b"]
AMOUNT_PATS = [r"\b(\d+[\.,]?\d*)\s*€\b", r"\b(\d+[\.,]?\d*)\s*(euros?)\b"]

def _extract_all(pats,text,flags=0):
    seen, out = set(), []
    import re
    for p in pats:
        for m in re.finditer(p,text,flags=flags):
            s=m.group(0)
            if s not in seen:
                seen.add(s); out.append(s)
    return out

def extract_dates(t): return _extract_all(DATE_PATS,t,flags=re.I)
def extract_times(t): return [x.replace("H","h") for x in _extract_all(TIME_PATS,t)]
def extract_amounts(t):
    import re
    seen,out=set(),[]
    for p in AMOUNT_PATS:
        for m in re.finditer(p,t,flags=re.I):
            a=m.group(1).replace(",",".")
            if a not in seen: seen.add(a); out.append(a)
    return out

def is_important(t): 
    low=t.lower()
    return any(k.lower() in low for k in IMPORTANT_KEYWORDS)

def pick_vibe(t):
    low=t.lower()
    keys=["Hugo","Axel","tribunal","pension","paiement","virement","malade",
          "scolaire","extrascolaire","rdv","rendez-vous","collège","lycée","CAF","€","euro"]
    hits=[k for k in keys if k.lower() in low]
    if not hits: return "Message reçu, tout roule comme sur des roulettes 🛼"
    key=hits[0]
    if key in ["rendez-vous","rdv","collège","lycée"]: key="rdv"
    return random.choice(GOOD_VIBES.get(key, ["Message reçu, tout roule comme sur des roulettes 🛼"]))

def build_summary(body):
    vibe=pick_vibe(body)
    d,t,a=extract_dates(body),extract_times(body),extract_amounts(body)
    parts=[]
    if d: parts.append("RDV "+", ".join(d))
    if t: parts.append("à "+", ".join(t))
    if a: parts.append("montant "+", ".join([x+" €" if not x.endswith("€") else x for x in a]))
    info=" — ".join(parts) if parts else "Pas de détail critique"
    return f"{vibe} — {info}", d, t, a

def pick_reply(body, d, t, a):
    low=body.lower()
    if any(k in low for k in ["virement","paiement","pension","€","euro","montant"]):
        amt=a[0]+" €" if a else ""
        return f"Bien reçu. Je prévois le virement {('de ' + amt) if amt else ''} rapidement."
    if any(k in low for k in ["rendez-vous","rdv","collège","lycée","reunion","réunion"]):
        dd=d[0] if d else "bientôt"; tt=t[0] if t else ""
        when=f"le {dd}"+(f" à {tt}" if tt else "")
        return f"Bien reçu. {when} est noté."
    return "Bien reçu, merci pour l’information."

# --- Gmail helpers (Render: creds/token via env) ---
def _build_service():
    cred_json=os.getenv("CREDENTIALS_JSON","")
    token_json=os.getenv("TOKEN_JSON","")
    if not cred_json or not token_json:
        raise RuntimeError("Missing CREDENTIALS_JSON or TOKEN_JSON env var.")
    # écrire fichiers (la lib aime bien les fichiers pour refresh)
    with open("credentials.json","w",encoding="utf-8") as f: f.write(cred_json)
    with open("token.json","w",encoding="utf-8") as f: f.write(token_json)

    creds=Credentials.from_authorized_user_info(json.loads(token_json), scopes=[
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send"])
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail","v1",credentials=creds)

def _get_label_id(s, name):
    labs=s.users().labels().list(userId="me").execute().get("labels",[])
    for lab in labs:
        if lab["name"]==name: return lab["id"]
    created=s.users().labels().create(userId="me",
        body={"name":name,"labelListVisibility":"labelShow","messageListVisibility":"show"}).execute()
    return created["id"]

def _list_unread(s):
    return s.users().messages().list(userId="me", q="is:unread", maxResults=50).execute().get("messages",[])

def _get_msg(s, mid):
    return s.users().messages().get(userId="me", id=mid, format="full").execute()

def _body_text(msg):
    data=""; p=msg.get("payload",{})
    parts=p.get("parts",[])
    if parts:
        for part in parts:
            if part.get("mimeType","").startswith("text/plain"):
                data=part.get("body",{}).get("data",""); break
            if part.get("mimeType","").startswith("text/html") and not data:
                data=part.get("body",{}).get("data","")
    else:
        data=p.get("body",{}).get("data","")
    try: return base64.urlsafe_b64decode(data.encode()).decode("utf-8","ignore")
    except: return ""

def _modify(s, mid, add=None, rem=None):
    s.users().messages().modify(userId="me", id=mid,
        body={"addLabelIds":add or [], "removeLabelIds":rem or []}).execute()

def _send(s, to, subject, body, thread_id=None, in_reply_to=None, references=None):
    msg=MIMEText(body); msg["to"]=to; msg["subject"]=subject
    if in_reply_to: msg["In-Reply-To"]=in_reply_to
    if references: msg["References"]=references
    raw=base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload={"raw":raw}; 
    if thread_id: payload["threadId"]=thread_id
    s.users().messages().send(userId="me", body=payload).execute()

def run_email_master():
    processed=0
    try:
        s=_build_service()
        label_id=_get_label_id(s, TARGET_LABEL)
        msgs=_list_unread(s) or []
        for m in msgs:
            full=_get_msg(s, m["id"])
            headers={h["name"].lower():h["value"] for h in full.get("payload",{}).get("headers",[])}
            sender=headers.get("from","")
            subject=headers.get("subject","(sans objet)")
            message_id=headers.get("message-id")
            thread_id=full.get("threadId")
            body=_body_text(full)

            # filtre Laure uniquement
            if LAURE_EMAILS and not any(e.lower() in sender.lower() for e in LAURE_EMAILS):
                continue

            # tout va dans Picsouille (retire INBOX/UNREAD)
            _modify(s, m["id"], add=[label_id], rem=["UNREAD","INBOX"])

            if is_important(body):
                summary, d, t, a = build_summary(body)
                if SEND_SUMMARY_TO:
                    _send(s, SEND_SUMMARY_TO, f"[Good Vibes] {subject}", summary)
                # auto-reply
                to_addr=sender
                try:
                    mm=re.search(r"<([^>]+)>", sender)
                    if mm: to_addr=mm.group(1)
                except: pass
                reply=pick_reply(body,d,t,a)
                _send(s, to_addr, f"Re: {subject}", reply, thread_id=thread_id,
                      in_reply_to=message_id, references=message_id)
            processed+=1
    except HttpError as e:
        print("Gmail API error:", e, flush=True)
    except Exception as e:
        print("Error:", e, flush=True)
    return processed
