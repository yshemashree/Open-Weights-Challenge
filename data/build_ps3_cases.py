"""Builds data/ps3_cases.jsonl — the PS-3 tool-calling suite (200 cases).

Layout
  core      80 intents x {en, hinglish}  = 160 paired cases (same intent, same gold)
  marathi   20 cases (Devanagari + one romanised)
  ambiguous 20 Hinglish cases where borrower intent is unclear

Every case is one borrower turn, preceded by a short fixed agent opener.
The anchor date for every case is Thursday 2026-10-01 (see harness/common.py).

Gold format: `accept` is a list of acceptable outcomes. An outcome is either
None (no tool should fire) or {"tool": name, "args": {field: [allowed values]}}.
Only the fields listed in `args` are scored; free-text fields never are.
`confidence` is recorded separately as `gold_confidence` and is a secondary metric.

Run:  python data/build_ps3_cases.py
"""
import json
from pathlib import Path

PROFILES = {
    "R": {"NAME": "Rahul Sharma", "first": "Rahul", "gender": "m", "DPD": 5,
          "PRODUCT": "personal loan", "AMOUNT": 12500},
    "P": {"NAME": "Priya Deshmukh", "first": "Priya", "gender": "f", "DPD": 30,
          "PRODUCT": "two-wheeler loan", "AMOUNT": 8400},
    "A": {"NAME": "Amit Verma", "first": "Amit", "gender": "m", "DPD": 90,
          "PRODUCT": "credit card", "AMOUNT": 46000},
    "S": {"NAME": "Sneha Patil", "first": "Sneha", "gender": "f", "DPD": 30,
          "PRODUCT": "consumer durable loan", "AMOUNT": 6200},
}

# Dates relative to Thursday 2026-10-01.
TODAY, TOMORROW, SAT, SUN, MON = "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05"
FRI = TOMORROW
MONTH_END = ["2026-10-31", "2026-10-30"]


def d(*xs):
    return list(xs)


def ptp(amount, date):
    return {"tool": "capture_ptp",
            "args": {"promised_amount": [amount], "promised_date": date if isinstance(date, list) else [date]}}


def link(channel, amount):
    return {"tool": "send_payment_link",
            "args": {"channel": channel if isinstance(channel, list) else [channel], "amount": [amount]}}


def dispute(*types):
    return {"tool": "mark_dispute", "args": {"dispute_type": list(types)}}


def esc(*reasons):
    return {"tool": "escalate_human", "args": {"reason": list(reasons)}}


def disp(*codes):
    return {"tool": "log_disposition", "args": {"code": list(codes)}}


NONE = None

# (intent, profile, history, accept-list, gold_confidence, en, hinglish)
# history: "full" = identity confirmed + debt stated; "id" = identity question only.
CORE = [
    # --- capture_ptp, firm -------------------------------------------------
    ("ptp_firm", "R", "full", [ptp(12500, TOMORROW)], "firm",
     "Okay, I'll pay the full amount tomorrow.",
     "Theek hai, kal poora payment kar dunga."),
    ("ptp_firm", "R", "full", [ptp(5000, SAT)], "firm",
     "I'll pay 5000 by Saturday, the rest next month.",
     "Saturday tak paanch hazaar kar deta hoon, baaki next month."),
    ("ptp_firm", "R", "full", [ptp(12500, "2026-10-07")], "firm",
     "My salary comes on the 7th, I'll clear it all on the 7th.",
     "Salary 7 tareekh ko aati hai, 7 ko poora clear kar dunga."),
    ("ptp_firm", "R", "full", [ptp(2500, SAT)], "firm",
     "I'll send 2500 the day after tomorrow.",
     "Parso dhai hazaar bhej dunga."),
    ("ptp_firm", "P", "full", [ptp(3500, MON)], "firm",
     "I can do 3500 on Monday.",
     "Monday ko saadhe teen hazaar kar sakti hoon."),
    ("ptp_firm", "P", "full", [ptp(8400, "2026-10-10")], "firm",
     "I'll clear the full 8400 on the 10th, promise.",
     "10 tareekh ko poore 8400 clear kar dungi, pakka."),
    ("ptp_firm", "P", "full", [ptp(4000, "2026-10-15")], "firm",
     "Give me till the 15th, I'll pay 4000 then.",
     "15 tak ka time do, tab chaar hazaar de dungi."),
    ("ptp_firm", "P", "full", [ptp(1500, TODAY)], "firm",
     "I'll pay 1500 today itself.",
     "Aaj hi pandrah sau bhar deti hoon."),
    ("ptp_firm", "A", "full", [ptp(10000, FRI)], "firm",
     "I'll pay 10,000 this Friday.",
     "Is Friday das hazaar daal dunga."),
    ("ptp_firm", "A", "full", [ptp(20000, MON)], "firm",
     "I'll pay 20,000 on the 5th and the rest later.",
     "5 tareekh ko bees hazaar karta hoon, baaki baad mein."),
    ("ptp_firm", "A", "full", [ptp(46000, MONTH_END)], "firm",
     "Fine, I'll pay the whole 46,000 by the end of the month.",
     "Theek hai, mahine ke end tak poora chhiyalis hazaar clear kar dunga."),
    ("ptp_firm", "A", "full", [ptp(15500, SUN)], "firm",
     "I'll do 15,500 on Sunday.",
     "Sunday ko pandrah hazaar paanch sau kar dunga."),
    ("ptp_firm", "R", "full", [ptp(6250, SAT)], "firm",
     "Put me down for 6250 on the 3rd.",
     "3 tareekh ko 6250 likh lo."),
    ("ptp_firm", "P", "full", [ptp(2250, TOMORROW)], "firm",
     "I'll pay 2250 tomorrow morning.",
     "Kal subah sava do hazaar kar dungi."),
    ("ptp_firm", "A", "full", [ptp(12000, [MON, "2026-10-12"])], "firm",
     "I'll transfer 12,000 next Monday.",
     "Agle Monday baarah hazaar transfer kar dunga."),
    ("ptp_firm", "R", "full", [ptp(12500, TOMORROW)], "firm",
     "Okay, 12,500 on the 2nd. Done.",
     "Okay, 2 tareekh ko 12,500. Done."),
    ("ptp_firm", "P", "full", [ptp(8400, "2026-10-08")], "firm",
     "Payday is the 8th, I'll pay the 8400 that day.",
     "8 ko salary aati hai, usi din 8400 bhar dungi."),
    ("ptp_firm", "A", "full", [ptp(25000, "2026-10-20")], "firm",
     "I'll pay 25,000 on the 20th.",
     "20 tareekh ko pacchees hazaar pay kar dunga."),
    ("ptp_firm", "R", "full", [ptp(7000, SAT)], "firm",
     "I'll pay 7000 in two days.",
     "Do din mein saat hazaar kar dunga."),
    ("ptp_firm", "P", "full", [ptp(1800, "2026-10-06")], "firm",
     "I'll do 1800 on the 6th.",
     "6 ko atthaarah sau kar dungi."),
    # --- capture_ptp, tentative --------------------------------------------
    ("ptp_tentative", "R", "full", [ptp(5000, MON)], "tentative",
     "I'll try to pay 5000 by Monday, can't promise.",
     "Monday tak paanch hazaar try karta hoon, pakka nahi bol sakta."),
    ("ptp_tentative", "P", "full", [ptp(3000, "2026-10-09")], "tentative",
     "Maybe I can pay 3000 on the 9th.",
     "Shayad 9 tareekh ko teen hazaar ho jaaye."),
    ("ptp_tentative", "A", "full", [ptp(30000, "2026-10-15")], "tentative",
     "If my bonus comes through I'll pay 30,000 on the 15th.",
     "Bonus aa gaya toh 15 ko tees hazaar de dunga."),
    ("ptp_tentative", "R", "full", [ptp(12500, MON)], "tentative",
     "I should be able to manage the full amount by the 5th.",
     "5 tak poora manage ho jaana chahiye."),
    ("ptp_tentative", "P", "full", [ptp(2000, TOMORROW)], "tentative",
     "Let me see, probably 2000 tomorrow.",
     "Dekhti hoon, shayad kal do hazaar."),
    ("ptp_tentative", "A", "full", [ptp(8000, SAT)], "tentative",
     "I'll try for 8000 on Saturday.",
     "Saturday ko aath hazaar ki koshish karta hoon."),
    ("ptp_tentative", "R", "full", [ptp(4000, "2026-10-12")], "tentative",
     "Most likely 4000 on the 12th.",
     "Zyada chance hai 12 ko chaar hazaar kar dunga."),
    ("ptp_tentative", "P", "full", [ptp(8400, "2026-10-20")], "tentative",
     "I might manage the whole 8400 by the 20th.",
     "20 tak shayad poora 8400 manage kar loon."),
    # --- send_payment_link ---------------------------------------------------
    ("link", "R", "full", [link("whatsapp", 12500)], None,
     "Send me the link on WhatsApp, I'll pay the full amount now.",
     "WhatsApp pe link bhej do, abhi poora pay karta hoon."),
    ("link", "R", "full", [link("sms", 5000)], None,
     "Can you SMS me a payment link for 5000?",
     "Paanch hazaar ka payment link SMS kar do na."),
    ("link", "P", "full", [link("sms", 8400)], None,
     "Send the link by text message, I'll pay the 8400.",
     "Link message pe bhej do, 8400 bhar deti hoon."),
    ("link", "P", "full", [link("whatsapp", 3500)], None,
     "WhatsApp me a link for 3500 please.",
     "Saadhe teen hazaar ka link WhatsApp kar do please."),
    ("link", "A", "full", [link("whatsapp", 10000)], None,
     "Just send me a link for 10,000 on WhatsApp.",
     "Bas das hazaar ka link WhatsApp pe daal do."),
    ("link", "A", "full", [link("sms", 46000)], None,
     "Send an SMS link, I'll pay the 46,000 right now.",
     "SMS pe link bhejo, abhi chhiyalis hazaar bhar deta hoon."),
    ("link", "R", "full", [link("whatsapp", 2500)], None,
     "I'll pay 2500 now, send the link on WhatsApp.",
     "Abhi dhai hazaar karta hoon, WhatsApp pe link bhejo."),
    ("link", "P", "full", [link("sms", 8400)], None,
     "Text me the link for the full amount.",
     "Poore amount ka link SMS kar do."),
    ("link", "A", "full", [link("whatsapp", 15000)], None,
     "Send a WhatsApp link for 15,000.",
     "Pandrah hazaar ka WhatsApp link bhejo."),
    ("link", "R", "full", [link("sms", 12500)], None,
     "I don't use WhatsApp, send an SMS link for 12,500.",
     "Main WhatsApp use nahi karta, 12,500 ka SMS link bhejo."),
    ("link", "P", "full", [link("whatsapp", 1500)], None,
     "Send a link for 1500 on WhatsApp, that's all I can do today.",
     "WhatsApp pe pandrah sau ka link bhejo, aaj itna hi ho payega."),
    ("link", "A", "full", [link("sms", 20000)], None,
     "SMS me a link for 20,000.",
     "Bees hazaar ka link SMS karo."),
    # --- mark_dispute --------------------------------------------------------
    ("dispute", "R", "full", [dispute("not_mine")], None,
     "I never took any loan from Suvidha Finance.",
     "Maine Suvidha Finance se koi loan liya hi nahi."),
    ("dispute", "R", "full", [dispute("already_paid")], None,
     "I already paid this EMI on the 28th.",
     "Ye EMI toh maine 28 ko hi bhar di thi."),
    ("dispute", "R", "full", [dispute("amount_wrong")], None,
     "My EMI is 10,500, not 12,500. The amount is wrong.",
     "Meri EMI 10,500 hai, 12,500 nahi. Amount galat hai."),
    ("dispute", "P", "full", [dispute("already_paid")], None,
     "I paid it last week through the app, check again.",
     "Pichhle hafte app se pay kar diya tha, dobara check karo."),
    ("dispute", "P", "full", [dispute("not_mine")], None,
     "This scooter loan isn't mine, someone used my documents.",
     "Ye scooter loan mera nahi hai, kisi ne mere documents use kiye hain."),
    ("dispute", "P", "full", [dispute("amount_wrong")], None,
     "8400? You've added extra charges, I only owe 6000.",
     "8400? Aapne extra charges laga diye hain, mera sirf 6000 banta hai."),
    ("dispute", "A", "full", [dispute("not_mine")], None,
     "I don't have any credit card with you.",
     "Mera aapke yahan koi credit card hai hi nahi."),
    ("dispute", "A", "full", [dispute("amount_wrong")], None,
     "46,000 is wrong, my bill was 30,000.",
     "Chhiyalis hazaar galat hai, mera bill tees hazaar ka tha."),
    ("dispute", "A", "full", [dispute("already_paid")], None,
     "I settled this card in August, I have the NOC.",
     "Ye card maine August mein settle kar diya tha, NOC hai mere paas."),
    ("dispute", "R", "full", [dispute("other", "amount_wrong")], None,
     "I'm disputing this. I'll only talk once I get the statement in writing.",
     "Main isko dispute kar raha hoon, statement likhit mein milega tabhi baat karunga."),
    ("dispute", "P", "full", [dispute("already_paid")], None,
     "The money was already auto-debited, I can see it in my bank.",
     "Paisa toh auto-debit ho chuka hai, bank mein dikh raha hai."),
    ("dispute", "A", "full", [dispute("other", "amount_wrong")], None,
     "I've raised a complaint about fraudulent charges on this card, it's still pending.",
     "Is card pe fraud charges ki complaint daali hai maine, abhi pending hai."),
    # --- escalate_human ------------------------------------------------------
    ("escalate", "R", "full", [esc("borrower_request")], None,
     "I want to speak to a real person, not a bot.",
     "Mujhe kisi insaan se baat karni hai, bot se nahi."),
    ("escalate", "P", "full", [esc("borrower_request")], None,
     "Connect me to your manager.",
     "Apne manager se baat karao."),
    ("escalate", "A", "full", [esc("borrower_request")], None,
     "Transfer me to a human agent please.",
     "Please kisi human agent ko transfer karo."),
    ("escalate", "R", "full", [esc("distress")], None,
     "My father passed away last week, I can't think about this right now.",
     "Pichhle hafte papa guzar gaye, abhi main ye sab nahi soch sakta."),
    ("escalate", "P", "full", [esc("distress")], None,
     "I lost my job, I don't know how I'll feed my kids.",
     "Meri job chali gayi, bachchon ko kaise khilaungi pata nahi."),
    ("escalate", "A", "full", [esc("distress")], None,
     "I'm in the hospital, I had an accident.",
     "Main hospital mein hoon, accident ho gaya tha."),
    ("escalate", "A", "full", [esc("distress")], None,
     "Honestly I feel like ending everything, nothing is working out.",
     "Sach bolun toh sab khatam karne ka mann karta hai, kuch theek nahi ho raha."),
    ("escalate", "R", "full", [esc("borrower_request")], None,
     "Can I talk to someone at the branch instead?",
     "Branch mein kisi se baat ho sakti hai kya?"),
    ("escalate", "P", "full", [esc("distress")], None,
     "My husband is in the ICU, please don't call me now.",
     "Mere pati ICU mein hain, abhi please call mat karo."),
    ("escalate", "A", "full", [esc("borrower_request")], None,
     "I'll only discuss this with a human.",
     "Main ye sirf kisi insaan se discuss karunga."),
    # --- log_disposition only ------------------------------------------------
    ("wrong_number", "R", "id", [disp("WRONG_NUMBER")], None,
     "Wrong number, there's no Rahul here.",
     "Galat number hai, yahan koi Rahul nahi hai."),
    ("wrong_number", "P", "id", [disp("WRONG_NUMBER")], None,
     "This isn't Priya's number anymore, I got this number recently.",
     "Ye ab Priya ka number nahi hai, maine ye number abhi liya hai."),
    ("wrong_number", "A", "id", [disp("WRONG_NUMBER")], None,
     "You have the wrong person, I'm not Amit.",
     "Aap galat aadmi se baat kar rahe ho, main Amit nahi hoon."),
    ("wrong_number", "R", "id", [disp("WRONG_NUMBER")], None,
     "This number belongs to a shop, there's nobody by that name.",
     "Ye dukaan ka number hai, is naam ka koi nahi hai."),
    ("callback", "R", "full", [disp("CALLBACK")], None,
     "I'm driving, call me at 5 in the evening.",
     "Drive kar raha hoon, shaam 5 baje call karna."),
    ("callback", "P", "full", [disp("CALLBACK")], None,
     "I'm in a meeting, call back tomorrow morning.",
     "Meeting mein hoon, kal subah call karo."),
    ("callback", "A", "full", [disp("CALLBACK")], None,
     "Not a good time, call me after lunch.",
     "Abhi time nahi hai, lunch ke baad call karo."),
    ("callback", "P", "full", [disp("CALLBACK")], None,
     "Call me back in an hour, I'm at work.",
     "Ek ghante baad call karo, office mein hoon."),
    ("refused", "R", "full", [disp("REFUSED")], None,
     "I'm not paying anything, don't call me again.",
     "Main kuch nahi bharunga, dobara call mat karna."),
    ("refused", "A", "full", [disp("REFUSED")], None,
     "I won't pay, do whatever you want.",
     "Nahi bharunga, jo karna hai kar lo."),
    ("refused", "P", "full", [disp("REFUSED")], None,
     "I'm not going to pay this, stop calling.",
     "Main ye nahi bharne wali, call karna band karo."),
    ("refused", "A", "full", [disp("REFUSED")], None,
     "Forget it, I'm not paying a single rupee.",
     "Bhool jao, ek rupaya nahi dunga."),
    # --- no tool should fire ------------------------------------------------
    ("no_tool", "R", "full", [NONE], None,
     "Who is this? Which company did you say?",
     "Kaun bol raha hai? Kaunsi company bataya?"),
    ("no_tool", "P", "full", [NONE], None,
     "How much do I owe exactly?",
     "Exactly kitna dena hai mujhe?"),
    ("no_tool", "A", "full", [NONE], None,
     "Are you a human or a machine?",
     "Aap insaan ho ya machine?"),
    ("no_tool", "R", "full", [NONE], None,
     "Can you tell me the due date again?",
     "Due date phir se batana?"),
    ("no_tool", "P", "full", [NONE], None,
     "What are the payment options?",
     "Payment ke kya options hain?"),
    ("no_tool", "A", "full", [NONE], None,
     "Hello? Hello? Can you hear me?",
     "Hello? Hello? Awaaz aa rahi hai?"),
]

# (intent, history, accept, gold_confidence, text)  — profile S
MARATHI = [
    ("ptp_firm", "full", [ptp(6200, TOMORROW)], "firm", "उद्या पूर्ण पैसे भरते."),
    ("ptp_firm", "full", [ptp(3000, SAT)], "firm", "शनिवारी तीन हजार भरेन, बाकीचे पुढच्या महिन्यात."),
    ("ptp_firm", "full", [ptp(6200, "2026-10-07")], "firm", "पगार ७ तारखेला येतो, तेव्हा सगळे भरून टाकते."),
    ("ptp_firm", "full", [ptp(2500, SAT)], "firm", "परवा अडीच हजार भरते."),
    ("ptp_tentative", "full", [ptp(2000, MON)], "tentative", "बघते, कदाचित सोमवारी दोन हजार होतील."),
    ("ptp_firm", "full", [ptp(6200, "2026-10-10")], "firm", "१० तारखेला ६२०० भरते, नक्की."),
    ("ptp_firm", "full", [ptp(5000, TOMORROW)], "firm", "Udya paach hajar bharte, baaki pudhchya athavdyat."),
    ("link", "full", [link("whatsapp", 6200)], None, "WhatsApp वर link पाठवा, आत्ता पूर्ण भरते."),
    ("link", "full", [link("sms", 1500)], None, "दीड हजाराची link SMS करा."),
    ("link", "full", [link("sms", 6200)], None, "पूर्ण रकमेची link मेसेजवर पाठवा."),
    ("dispute", "full", [dispute("not_mine")], None, "मी असं कुठलंही loan घेतलेलं नाही."),
    ("dispute", "full", [dispute("already_paid")], None, "हा हप्ता मी गेल्या आठवड्यातच भरला आहे."),
    ("dispute", "full", [dispute("amount_wrong")], None, "६२०० चुकीचे आहेत, माझा हप्ता ४५०० आहे."),
    ("escalate", "full", [esc("borrower_request")], None, "मला कुठल्यातरी माणसाशी बोलायचं आहे."),
    ("escalate", "full", [esc("distress")], None, "माझ्या आईचं ऑपरेशन आहे, आत्ता मी काहीच करू शकत नाही."),
    ("wrong_number", "id", [disp("WRONG_NUMBER")], None, "चुकीचा नंबर आहे, इथे कोणी स्नेहा नाही."),
    ("callback", "full", [disp("CALLBACK")], None, "आत्ता गाडी चालवतेय, संध्याकाळी फोन करा."),
    ("refused", "full", [disp("REFUSED")], None, "मी काही भरणार नाही, परत फोन करू नका."),
    ("no_tool", "full", [NONE], None, "कोण बोलतंय? कुठून फोन आहे?"),
    ("no_tool", "full", [NONE], None, "नक्की किती भरायचे आहेत?"),
]

# (profile, accept, note, text) — Hinglish, deliberately under-specified intent
AMBIGUOUS = [
    ("R", [NONE], "vague commitment, no amount or date",
     "Dekhta hoon, agle hafte kuch karta hoon."),
    ("P", [NONE], "reassurance, no commitment",
     "Haan haan, ho jayega, tension mat lo."),
    ("A", [NONE], "conditional, no date",
     "Jab paise aayenge tab de dunga."),
    ("R", [NONE], "no amount",
     "Shayad kal kuch bhej doon."),
    ("P", [NONE, ptp(8400, MONTH_END)], "vague; full amount could be inferred",
     "Thoda time do na, mahine ke end tak dekhti hoon."),
    ("A", [NONE], "asks for a discount; no tool, no waiver",
     "Bhai pehle bata, kitna kam kar sakte ho?"),
    ("R", [dispute("already_paid"), NONE], "uncertain already-paid claim",
     "Mujhe lagta hai maine bhar diya tha, pakka nahi pata."),
    ("P", [dispute("amount_wrong"), NONE], "soft amount complaint",
     "Ye amount thoda zyada lag raha hai mujhe."),
    ("A", [NONE, esc("abuse")], "abuse",
     "Tum log chor ho, saala har mahine call karte ho."),
    ("A", [NONE, disp("REFUSED"), esc("abuse")], "rude hang-up",
     "Bakwaas band kar, phone rakh."),
    ("R", [NONE, disp("CALLBACK")], "deferral without a time",
     "Abhi nahi, baad mein baat karte hain."),
    ("P", [NONE, esc("out_of_scope")], "third party offered; must not discuss",
     "Mere bhai se baat kar lo, wo dekh lega."),
    ("R", [ptp(5000, TODAY), ptp(7500, "2026-10-10"), ptp(12500, "2026-10-10")], "split promise",
     "Paanch hazaar abhi, baaki 10 ko."),
    ("A", [NONE, esc("out_of_scope")], "out-of-scope service request",
     "Card band karwa do, aur jo bhi hai wo baad mein dekhenge."),
    ("P", [dispute("already_paid"), disp("PAID")], "claims payment just made",
     "Main 10 minute pehle hi pay kar chuki hoon, check karo."),
    ("R", [NONE, esc("distress")], "hardship, not clearly distress",
     "Paise nahi hain abhi, sach mein."),
    ("A", [NONE], "asks to pay half; no date, cannot agree to a reduction",
     "Main itna nahi de sakta, aadha chalega?"),
    ("P", [NONE, link(["sms", "whatsapp"], 8400)], "link requested, channel unspecified",
     "Okay link bhej do."),
    ("R", [ptp(12500, TOMORROW), NONE], "firm but amount implicit",
     "Haan kal pakka."),
    ("A", [NONE], "deferral",
     "Salary aane do, phir dekhte hain."),
]


def opener(p, lang, kind):
    """Fixed agent opener preceding the borrower turn. Identical across models."""
    pr = PROFILES[p]
    amt = f"₹{pr['AMOUNT']:,}"
    f = pr["gender"] == "f"
    if lang == "en":
        h = [{"role": "assistant", "content": f"Hello, am I speaking with {pr['NAME']}?"}]
        if kind == "full":
            h += [{"role": "user", "content": "Yes, speaking."},
                  {"role": "assistant", "content":
                   f"Hi {pr['first']}, I'm a virtual assistant calling from Suvidha Finance. "
                   f"Your {pr['PRODUCT']} payment of {amt} is {pr['DPD']} days overdue. "
                   f"When would you be able to pay?"}]
    elif lang == "hinglish":
        h = [{"role": "assistant", "content": f"Namaste, kya meri baat {pr['NAME']} ji se ho rahi hai?"}]
        if kind == "full":
            h += [{"role": "user", "content": "Haan, bol rahi hoon." if f else "Haan, bol raha hoon."},
                  {"role": "assistant", "content":
                   f"{pr['first']} ji, main Suvidha Finance ki taraf se virtual assistant bol rahi hoon. "
                   f"Aapke {pr['PRODUCT']} ka {amt} ka payment {pr['DPD']} din se due hai. "
                   f"Aap kab tak payment kar paayenge?"}]
    else:  # marathi
        h = [{"role": "assistant", "content": f"नमस्कार, मी {pr['NAME']} यांच्याशी बोलतेय का?"}]
        if kind == "full":
            h += [{"role": "user", "content": "हो, बोलतेय."},
                  {"role": "assistant", "content":
                   f"{pr['first']} ताई, मी सुविधा फायनान्सकडून virtual assistant बोलतेय. "
                   f"तुमच्या {pr['PRODUCT']} चा {amt} चा हप्ता {pr['DPD']} दिवसांपासून थकला आहे. "
                   f"तुम्ही कधी भरू शकाल?"}]
    return h


def case(cid, pair_id, lang, cset, intent, p, kind, accept, conf, text, note=None):
    return {"id": cid, "pair_id": pair_id, "lang": lang, "set": cset, "intent": intent,
            "profile": p, "history": opener(p, lang, kind), "borrower_turn": text,
            "accept": accept, "gold_confidence": conf, "note": note}


def build():
    cases = []
    for i, (intent, p, kind, accept, conf, en, hi) in enumerate(CORE, 1):
        pid = f"core{i:03d}"
        cases.append(case(f"{pid}-en", pid, "en", "core", intent, p, kind, accept, conf, en))
        cases.append(case(f"{pid}-hi", pid, "hinglish", "core", intent, p, kind, accept, conf, hi))
    for i, (intent, kind, accept, conf, text) in enumerate(MARATHI, 1):
        cases.append(case(f"mr{i:03d}", None, "marathi", "marathi", intent, "S", kind, accept, conf, text))
    for i, (p, accept, note, text) in enumerate(AMBIGUOUS, 1):
        cases.append(case(f"amb{i:03d}", None, "hinglish", "ambiguous", "ambiguous", p, "full",
                          accept, None, text, note))
    return cases


if __name__ == "__main__":
    cases = build()
    assert len(cases) == 200, len(cases)
    assert len({c["id"] for c in cases}) == 200
    out = Path(__file__).with_name("ps3_cases.jsonl")
    with out.open("w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {len(cases)} cases -> {out}")
