"""Pages built from the approved redesign rather than converted from WordPress.

Each spec may set title, template, seo_title, seo_description, menu_title and a build(placeholders, wp, ctx)
function that fills the page with ISU-ARMAC content blocks. Editors can change everything afterwards in the CMS.
"""
import json
from functools import lru_cache
from pathlib import Path

from cms.api import add_plugin
from django.conf import settings

from .content_fixes import apply_fixes
from .navigation import CI, IC, PC, PL
from .wp_clean import clean_title, page_blocks, plain_text, site_path

L = "en"
PHOTO = "/static/img/photos/"
CACHE = Path(settings.BASE_DIR) / "import_cache"


@lru_cache(maxsize=1)
def wp_pages():
    return {site_path(p["link"]): p for p in json.loads((CACHE / "pages.json").read_text())}


@lru_cache(maxsize=1)
def wp_testimonials():
    quotes = []
    for path in ("/testimonials/", "/about-us/"):
        wp = wp_pages().get(path)
        if wp:
            for kind, value in page_blocks(wp["content"]["rendered"], "", set()):
                if kind == "testimonials":
                    quotes.extend((apply_fixes(q, url="/testimonials/") if path == "/testimonials/" else apply_fixes(q, url=path), who) for q, who in value)
    return quotes


def children_of(prefix):
    """WordPress pages one level below prefix, as (title, path), alphabetical."""
    depth = prefix.count("/") + 1
    out = []
    for path, wp in wp_pages().items():
        if path.startswith(prefix) and path != prefix and path.count("/") == depth:
            out.append((apply_fixes(clean_title(wp["title"]["rendered"])), path))
    return sorted(out)


# Small builders ---------------------------------------------------------------

def section(ph, **kw):
    return add_plugin(ph, "SectionPlugin", L, **kw)


def grid(ph, parent, columns, style):
    return add_plugin(ph, "CardGridPlugin", L, target=parent, columns=columns, style=style)


def card(ph, parent, title, **kw):
    return add_plugin(ph, "CardPlugin", L, target=parent, title=title, **kw)


def text(ph, parent, html):
    return add_plugin(ph, "TextPlugin", L, target=parent, body=html)


def wordpress_text(ph, parent, wp, ctx):
    """Append a WordPress page's text blocks and FAQs under parent (used on hub pages)."""
    if not wp:
        return
    url = site_path(wp["link"])
    for kind, value in page_blocks(wp["content"]["rendered"], clean_title(wp["title"]["rendered"]), ctx.images):
        if kind == "html" and plain_text(value):
            text(ph, parent, apply_fixes(value, url=url))
        elif kind == "faq":
            faq = add_plugin(ph, "FAQPlugin", L, target=parent)
            for i, (q, a) in enumerate(value):
                add_plugin(ph, "FAQItemPlugin", L, target=faq, question=apply_fixes(q, url=url)[:255],
                           answer=apply_fixes(plain_text(a), url=url), open=(i == 0))


def page_hero(ph, heading, sub="", badge="", primary=("Get a Quote", "/get-a-quote/"), secondary=None, image="", alt="", checks=""):
    return add_plugin(ph, "HeroPlugin", L, style="page", heading=heading, subheading=sub, badge=badge,
                      primary_text=primary[0] if primary else "", primary_url=primary[1] if primary else "",
                      secondary_text=secondary[0] if secondary else "", secondary_url=secondary[1] if secondary else "",
                      image_url=image, image_alt=alt, checklist=checks)


def cta_band(ph, heading="Let 300+ carriers compete for you", sub="Quotes for personal, business and group benefits."):
    add_plugin(ph, "CTABandPlugin", L, heading=heading, text=sub, primary_text="Get a Quote", primary_url="/get-a-quote/",
               secondary_text="Group Benefits Quote", secondary_url="/get-a-group-benefits-quote/")


# Homepage ----------------------------------------------------------------------

def build_home(phs, wp=None, ctx=None):
    ph = phs["content"]
    add_plugin(ph, "HeroPlugin", L, style="home", badge="Independent agency · 60+ years",
               heading="Coverage that fits.\nCarriers that compete for you.",
               subheading="ISU-ARMAC shops 300+ carriers for families, businesses and employers. Personal, commercial and employee benefits, all under one roof.",
               primary_text="Get a Quote", primary_url="/get-a-quote/",
               secondary_text="Call (760) 241-7900", secondary_url="tel:+17602417900")
    stats = add_plugin(ph, "StatsBandPlugin", L)
    for value, label in [("60+", "years serving clients"), ("300+", "carriers compared"), ("80+", "policy types"), ("All states", "licensed nationwide")]:
        add_plugin(ph, "StatPlugin", L, target=stats, value=value, label=label)

    s = section(ph, eyebrow="How we can help", heading="One agency for your home, your business and your people")
    g = grid(ph, s, 4, "service")
    card(ph, g, "Personal", icon="home", text="Protect your home, vehicles and the things you love.",
         links=f"Auto|{PL}/auto-insurance/\nHome|{PL}/home-insurance/\nFlood|{PL}/flood-insurance/\nEarthquake|{PL}/earthquake-insurance/\nBoat & Motorcycle|{PL}/boat-insurance/\nPet|{PL}/pet-insurance/",
         link_text="All personal coverage →", link_url=f"{PL}/")
    card(ph, g, "Private Client", icon="star", text="Tailored protection for significant homes and assets.",
         links=f"High Net Worth|{PC}/high-net-worth-insurance/\nValuable Possessions|{PC}/valuable-possessions-insurance/\nUmbrella|{PC}/umbrella-insurance/\nHigh Fire Risk|{PC}/high-fire-risk-insurance/\nIndividual Life|{PC}/individual-life-insurance/",
         link_text="All private client →", link_url=f"{PC}/")
    card(ph, g, "Business", icon="briefcase", text="Liability, property and workers' comp for every industry.",
         links=f"General Liability|{CI}/general-liability-insurance/\nWorkers' Compensation|{CI}/workers-compensation-insurance/\nCommercial Property|{CI}/commercial-property-insurance/\nCyber Liability|{CI}/cyber-liability-insurance/\nSurety Bonds|{CI}/surety-bonds/",
         link_text="All business coverage →", link_url=f"{CI}/")
    card(ph, g, "Employee Benefits", icon="people", text="Plans that help you hire, keep and care for your team.",
         links=f"Group Medical|{IC}/group-medical/\nGroup Dental|{IC}/group-dental/\nGroup Vision|{IC}/group-vision-template/\nGroup Life|{IC}/group-life/\nVoluntary Benefits|{IC}/group-voluntary-benefits/\n401(k)|{IC}/employee-benefits/401k/",
         link_text="All benefits →", link_url=f"{IC}/employee-benefits/")

    s = section(ph, background="navy", eyebrow="Specialty programs", heading="Deep expertise where the stakes are highest")
    g = grid(ph, s, 2, "program")
    card(ph, g, "Contractors & Construction", badge="CA · NV · AZ", image_url=PHOTO + "contractor-crew-framing.jpg",
         image_alt="A construction crew in hard hats framing a new home in the High Desert",
         text="General liability, workers' comp, bonds and crew benefits from one team. Free workers' comp and experience-mod review.",
         link_text="Explore contractor insurance", link_url=f"{CI}/contractor-insurance/")
    card(ph, g, "Independent Hospitals", badge="Nationwide", image_url=PHOTO + "hospital-exterior.jpg",
         image_alt="A community hospital emergency entrance with an ambulance at sunset",
         text="Property, casualty and employee benefits together, including management of your self-insured plan with our TPA partner.",
         link_text="Explore hospital programs", link_url=f"{CI}/hospital-insurance/")

    s = section(ph, background="sky", eyebrow="Industries", heading="Built for your business", link_text="See all industries →", link_url="/industries/")
    g = grid(ph, s, 4, "tile")
    for title, sub, url in [
        ("Contractors", "GL, comp, bonds", f"{CI}/contractor-insurance/"),
        ("Hospitals", "P&C and benefits", f"{CI}/hospital-insurance/"),
        ("Medical & Dental Offices", "Practice protection", f"{CI}/medical-office-insurance/"),
        ("Restaurants & Hospitality", "Bars, breweries, hotels", f"{CI}/restaurant-insurance/"),
        ("Manufacturing", "Products and plants", f"{CI}/manufacturer-insurance/"),
        ("Property Managers", "Portfolios and HOAs", f"{CI}/property-manager-insurance/"),
        ("Vacant Land", "Liability for open parcels", f"{CI}/vacant-land-insurance/"),
        ("Farm & Agriculture", "Crops, equipment, land", f"{CI}/farm-insurance/"),
    ]:
        card(ph, g, title, text=sub, link_url=url)

    s = section(ph)
    sp = add_plugin(ph, "SplitPlugin", L, target=s, image_url=PHOTO + "agent-consultation.jpg", image_alt="An ISU-ARMAC agent reviewing a policy with two clients",
                    eyebrow="Why ISU-ARMAC", heading="An independent agency that works for you",
                    text="We don't work for an insurance company. We work for you, shopping the market at every renewal and standing beside you when you file a claim.",
                    button_text="About our agency", button_url="/about-us/")
    for title, body in [
        ("We shop, you save time", "300+ carriers compete for your business, so you see real options."),
        ("One team, every policy", "Personal, business and benefits handled by people who know your file."),
        ("Claims advocacy", "When something goes wrong, call us first. We help you through it."),
        ("Local roots, national reach", "Based in Victorville, licensed to serve clients nationwide."),
    ]:
        card(ph, sp, title, text=body)

    s = section(ph, background="pale", compact=True)
    add_plugin(ph, "TeamStripPlugin", L, target=s)

    s = section(ph, two_columns=True)
    quotes = wp_testimonials()
    featured = next((q for q in quotes if "Britzman" in q[0]), quotes[0] if quotes else None)
    if featured:
        add_plugin(ph, "TestimonialPlugin", L, target=s, quote=featured[0], attribution=featured[1])
    add_plugin(ph, "LatestPostsPlugin", L, target=s, count=4)
    cta_band(ph)


# Contractor page ---------------------------------------------------------------

def build_contractor(phs, wp=None, ctx=None):
    ph = phs["hero"]
    page_hero(ph, "Contractor Insurance for California, Nevada and Arizona",
              sub="General liability, workers' comp, bonds and crew benefits from one agency that shops 300+ carriers for you.",
              badge="CALIFORNIA · NEVADA · ARIZONA", primary=("Get My Free Workers' Comp Review", "#quote"),
              secondary=("Call (760) 241-7900", "tel:+17602417900"), image=PHOTO + "contractor-roofer.jpg",
              alt="A roofing contractor holding a hard hat and tablet beside his work truck",
              checks="60+ years in business\n300+ carriers\nInsurance, bonds and benefits")
    ph = phs["content"]
    s = section(ph, compact=True)
    add_plugin(ph, "CalloutPlugin", L, target=s, eyebrow="Free review", heading="Are you overpaying for workers' comp?",
               text="Workers' comp is often a contractor's biggest insurance cost, and California rates are rising again in 2026. A wrong class code, an outdated experience mod or an overestimated payroll can add thousands a year without anyone noticing. Send us your policy and last audit, and a licensed agent will review your class codes, experience mod, payroll estimates and options from multiple carriers. It's free, with no obligation to switch.",
               button_text="Start My Free Review", button_url="#quote")

    s = section(ph, heading="Coverage we place for contractors",
                intro="One team handles your full program, so policies line up and renewals don't fall through the cracks.")
    g = grid(ph, s, 3, "plain")
    for title, body, extra in [
        ("General liability", "Injury or property damage to others from your work, including completed operations.", {}),
        ("Workers' compensation", "Medical bills and lost wages for injured employees.", {}),
        ("Commercial auto", "Your trucks, plus employees' personal vehicles used for work.", {}),
        ("Contractor's equipment", "Tools and equipment on the job, in transit or in storage.", {}),
        ("Builder's risk", "The structure while it's being built or renovated.", {}),
        ("Umbrella and excess", "Higher limits that general contractors and project owners require.", {}),
        ("License and surety bonds", "License, bid, performance and payment bonds.", {"link_text": "Surety bonds →", "link_url": f"{CI}/surety-bonds/", "highlight": True}),
        ("Pollution liability", "Mold, asbestos, fuel and runoff claims excluded from general liability.", {}),
        ("Group health and life", "Benefits that help you hire and keep good crews.", {"link_text": "Employee benefits →", "link_url": f"{IC}/employee-benefits/", "highlight": True}),
    ]:
        card(ph, g, title, text=body, **extra)

    s = section(ph, background="blue")
    add_plugin(ph, "PillListPlugin", L, target=s, heading="Trades we insure",
               intro="Don't see yours? Call us. With 300+ carriers, we can usually find a market.",
               items="Roofing\nConcrete & masonry\nElectrical\nPlumbing & HVAC\nFraming & carpentry\nSolar\nGrading & paving\nPainting & drywall\n"
                     f"Landscaping|{CI}/landscape-services-insurance/")
    s = section(ph, background="pale", heading="Where we work")
    g = grid(ph, s, 3, "soft")
    card(ph, g, "California", text="High Desert and Inland Empire to Los Angeles, San Diego and the Central Valley. CSLB certificates and bonds on file.")
    card(ph, g, "Nevada", text="Las Vegas, Henderson, Reno and beyond. Nevada State Contractors Board and large-project requirements.")
    card(ph, g, "Arizona", text="Phoenix, Tucson and the East Valley. Registrar of Contractors bond requirements.")

    s = section(ph, compact=True)
    add_plugin(ph, "CalloutPlugin", L, target=s, eyebrow="California · January 1, 2028",
               heading="Every California contractor will need workers' comp by 2028",
               text="Even with no employees. If you file an exemption today, we'll price coverage now so there's no surprise at your next license renewal.",
               button_text="Ask about the 2028 rule", button_url="#quote")

    s = section(ph, heading="Questions contractors ask")
    faq = add_plugin(ph, "FAQPlugin", L, target=s)
    for i, (q, a) in enumerate([
        ("How much does contractor insurance cost?", "It depends on your trade, payroll, revenue, location and claims history. Workers' comp is priced per $100 of payroll by class code. The fastest way to know is a quote: we compare multiple carriers at once."),
        ("Is workers' comp required for contractors?", "In California, Nevada and Arizona, businesses with employees must carry workers' comp. In California, all licensed contractors will need it starting January 1, 2028, whether or not they have employees."),
        ("What's the difference between insurance and a contractor bond?", "Insurance protects your business. A bond protects your customer or the state if you don't meet your obligations. Most licensed contractors need both, and we provide both."),
        ("Can you insure roofers and other high-risk trades?", "Yes. Roofing, framing and other higher-risk trades often get limited options from standard carriers. We work with specialty markets that write these trades."),
        ("How fast can I get a certificate of insurance?", "Once your policy is in force, usually the same business day. Call your account manager or email us."),
        ("I just got my contractor's license. Where do I start?", "Most new contractors need general liability, a license bond and, if they have employees, workers' comp. We'll set up all three and tell you what your first projects will likely require."),
    ]):
        add_plugin(ph, "FAQItemPlugin", L, target=faq, question=q, answer=a, open=(i == 0))
    s = section(ph, anchor="quote", compact=True)
    add_plugin(ph, "QuoteFormPlugin", L, target=s, form_type="contractor", heading="Get your contractor insurance quote",
               intro="A licensed agent will call you within one business day.", button_text="Get My Quote")
    if wp:
        s = section(ph, background="pale", heading="More about contractor insurance", prose=True)
        wordpress_text(ph, s, wp, ctx)


# Hospital page (new) -----------------------------------------------------------

def build_hospital(phs, wp=None, ctx=None):
    page_hero(phs["hero"], "Insurance and Employee Benefits for Independent Hospitals",
              sub="Property, casualty and employee benefits from one team, including management of your self-insured health plan with our TPA partner.",
              badge="INDEPENDENT HOSPITALS · NATIONWIDE", primary=("Talk to Our Healthcare Team", "#quote"),
              secondary=("Call (760) 241-7900", "tel:+17602417900"), image=PHOTO + "hospital-leaders-corridor.jpg",
              alt="A hospital executive and a nurse leader walking down a hospital corridor",
              checks="Trusted by multiple independent hospital groups\nP&C and employee benefits\nLicensed nationwide")
    ph = phs["content"]
    s = section(ph)
    sp = add_plugin(ph, "SplitPlugin", L, target=s, image_url=PHOTO + "hospital-nursing-station.jpg",
                    image_alt="Nurses and a physician at a hospital nursing station",
                    eyebrow="Why ISU-ARMAC", heading="Independent hospitals deserve an independent partner",
                    text="Independent hospitals carry the same risks as large health systems, without a system's buying power or a corporate risk department. One ISU-ARMAC team reviews your property and casualty program and your employee benefits together, so you see your full cost of risk in one place.")
    for title, body in [
        ("Hospital experience", "We work with multiple independent hospital groups."),
        ("Both lines, one team", "Property and casualty and employee benefits, reviewed together."),
        ("Self-insured plans", "We manage self-insured plans alongside our TPA partner."),
        ("Licensed nationwide", "Our team comes to you, wherever your hospital is."),
    ]:
        card(ph, sp, title, text=body)
    s = section(ph, background="pale", eyebrow="Property and casualty", heading="A risk program built for how hospitals operate",
                intro="Hospital liability remains one of the hardest insurance markets, while commercial property rates have been falling. We make sure you benefit from the soft markets and get the right structure in the hard ones.")
    g = grid(ph, s, 3, "plain")
    for title, body in [
        ("Hospital professional liability", "Claims arising from patient care, structured with the right limits, retentions and excess layers."),
        ("General liability and umbrella", "Injuries and property damage on your campus and in your clinics."),
        ("Property and business interruption", "Buildings, equipment and lost revenue after a fire, storm or outage."),
        ("Equipment breakdown", "Imaging, HVAC, generators and other critical systems."),
        ("Cyber liability", "Ransomware, data breaches, patient notification and system downtime."),
        ("Directors and officers", "Protection for your board and leadership."),
        ("Employment practices", "Wrongful termination, discrimination and harassment claims."),
        ("Workers' compensation", "Nurses, techs and support staff, who face frequent injuries from lifting and patient handling."),
        ("Crime and fiduciary", "Employee theft, fraud and benefit plan fiduciary exposure."),
    ]:
        card(ph, g, title, text=body)
    s = section(ph)
    g = add_plugin(ph, "SplitPlugin", L, target=s, image_url=PHOTO + "hospital-bedside.jpg",
                   image_alt="A nurse adjusting an IV pump for a smiling patient while a physician reviews a chart",
                   eyebrow="Employee benefits", heading="Benefits that keep your nurses and control your costs",
                   text="Your people are your largest expense and your hardest resource to replace. We design benefits that help you recruit and retain clinical staff while keeping plan costs predictable.")
    for title, body in [
        ("Medical, dental, vision and life", "Group plans built around a clinical workforce."),
        ("Self-funded and level-funded plans", "Plan design that keeps more of your claims dollars working for you."),
        ("Stop-loss insurance", "Marketed every year to keep large-claim protection competitive."),
        ("Pharmacy strategy", "Pharmacy benefit review and specialty drug strategy."),
        ("Steerage to your own care", "Plan designs that guide care to your own hospital and physicians."),
        ("Retention benefits", "Student loan help, childcare support and voluntary benefits."),
    ]:
        card(ph, g, title, text=body)
    s = section(ph, background="navy", eyebrow="Self-insured plan management",
                heading="We don't just quote your stop-loss. We manage your self-insured plan.",
                intro="ISU-ARMAC manages self-insured plans for hospitals, working alongside an experienced third-party administrator (TPA) that processes your claims. You get one point of contact for plan design, TPA oversight and stop-loss, claims reporting you can use, and early warning on large claims. Already self-funded? We'll review your current TPA arrangement and stop-loss contract at no cost.")
    s = section(ph, heading="How a review works")
    g = grid(ph, s, 3, "soft")
    for title, body in [
        ("1. Introductory call", "Thirty minutes to learn about your hospital, renewal dates and what's frustrating you today."),
        ("2. Data gathering", "You share current policies, loss runs and benefits claims reports under a confidentiality agreement."),
        ("3. Analysis", "We benchmark your program against hospitals like yours and test the market where it makes sense."),
        ("4. Findings meeting", "We walk your CFO, HR leader and, if you like, your board finance committee through what we found."),
        ("5. Your decision", "There's no obligation. Many hospitals start with one line and add the other at its renewal."),
    ]:
        card(ph, g, title, text=body)
    s = section(ph, background="pale", heading="Hospital questions")
    faq = add_plugin(ph, "FAQPlugin", L, target=s)
    for i, (q, a) in enumerate([
        ("Do you work with hospitals outside California?", "Yes. ISU-ARMAC is licensed nationwide and works with independent hospitals and hospital groups in many states. Our team comes to you."),
        ("Can you handle both our insurance and our benefits?", "Yes. We place both, and reviewing them together is where hospitals often find the most value. You can also start with one and add the other later."),
        ("We're self-funded today. Can you take over managing our plan?", "Yes. We'll review your current arrangement, plan the transition around your plan year and make sure your stop-loss and our TPA partner's claims administration line up."),
        ("Is self-funding right for a hospital our size?", "It depends on your workforce, claims history and appetite for risk. We'll run a feasibility analysis with your data and show the expected cost and the worst-case cost with stop-loss in place."),
        ("When should we start a review?", "Ideally four to six months before your renewal date. For a January 1 benefits renewal, that means talking by early summer."),
        ("Will this disrupt our current broker relationship?", "A review is confidential. You only make a change if the findings justify it."),
    ]):
        add_plugin(ph, "FAQItemPlugin", L, target=faq, question=q, answer=a, open=(i == 0))
    s = section(ph, anchor="quote", compact=True)
    add_plugin(ph, "QuoteFormPlugin", L, target=s, form_type="hospital", heading="Talk to our healthcare team",
               intro="Tell us about your hospital. A member of our healthcare team will reply within one business day.",
               button_text="Contact Our Healthcare Team")


# Hubs and listing pages --------------------------------------------------------

def hub_builder(heading, sub, prefix, intro_heading, extra_links=(), image="", alt=""):
    def build(phs, wp=None, ctx=None):
        page_hero(phs["hero"], heading, sub=sub, image=PHOTO + image if image else "", alt=alt)
        ph = phs["content"]
        s = section(ph, heading=intro_heading)
        g = grid(ph, s, 4, "tile")
        for title, path in list(children_of(prefix)) + list(extra_links):
            card(ph, g, title, link_url=path)
        if wp:
            s = section(ph, background="pale", prose=True)
            wordpress_text(ph, s, wp, ctx)
        cta_band(ph)
    return build


INDUSTRY_SLUGS = [
    "contractor-insurance", "hospital-insurance", "medical-office-insurance", "dental-office-insurance",
    "veterinary-office-insurance", "child-care-center-insurance", "non-profit-insurance", "restaurant-insurance",
    "night-club-and-bar-insurance", "brewery-insurance", "hospitality-insurance", "fitness-center-insurance",
    "golf-course-insurance", "retail-insurance", "office-risk-insurance", "technology-firm-insurance",
    "manufacturer-insurance", "garage-repair-shop-insurance", "dealership-insurance", "property-manager-insurance",
    "landscape-services-insurance", "aviation-insurance", "farm-insurance",
]


def build_industries(phs, wp=None, ctx=None):
    page_hero(phs["hero"], "Industries we insure",
              sub="Specialized coverage for more than 20 industries, from contractors and hospitals to restaurants, farms and nonprofits.",
              image=PHOTO + "industries-main-street.jpg", alt="A busy High Desert main street with restaurants, a medical office and a contractor's truck")
    ph = phs["content"]
    s = section(ph, heading="Find your industry")
    g = grid(ph, s, 4, "tile")
    pages = wp_pages()
    for slug in INDUSTRY_SLUGS:
        path = f"{CI}/{slug}/"
        title = "Hospitals" if slug == "hospital-insurance" else apply_fixes(clean_title(pages[path]["title"]["rendered"])) if path in pages else slug
        card(ph, g, title, link_url=path)
    cta_band(ph, heading="Don't see your industry?", sub="With 300+ carriers, we can usually find the right market. Call us or request a quote.")


def build_team(phs, wp=None, ctx=None):
    page_hero(phs["hero"], "Our team", sub="Licensed agents and account managers who know your file and answer the phone.",
              primary=("Contact us", "/contact/"))
    s = section(phs["content"])
    add_plugin(phs["content"], "TeamStripPlugin", L, target=s, heading="Meet the ISU-ARMAC team", show_all=True)
    s = section(phs["content"], background="pale", heading="Join our team", intro="We're always glad to meet licensed agents and service professionals who care about clients.",
                link_text="See open roles →", link_url="/join-our-team/")


def build_testimonials(phs, wp=None, ctx=None):
    page_hero(phs["hero"], "What our clients say", sub="Real words from the families and businesses we serve.")
    ph = phs["content"]
    s = section(ph)
    for quote, who in wp_testimonials():
        add_plugin(ph, "TestimonialPlugin", L, target=s, quote=quote, attribution=who)
    s = section(ph, background="pale", compact=True, heading="Had a good experience with us?",
                link_text="Leave a review →", link_url="/review-us/")


def form_page(heading, sub, form_type, form_heading, button):
    def build(phs, wp=None, ctx=None):
        page_hero(phs["hero"], heading, sub=sub, primary=None, secondary=("Call (760) 241-7900", "tel:+17602417900"))
        s = section(phs["content"], compact=True)
        add_plugin(phs["content"], "QuoteFormPlugin", L, target=s, form_type=form_type, heading=form_heading,
                   intro="A licensed agent will follow up within one business day.", button_text=button, dark=False)
    return build


def build_contact(phs, wp=None, ctx=None):
    page_hero(phs["hero"], "Contact ISU-ARMAC", sub="Call, email or send us a message. We answer within one business day.", primary=None,
              secondary=("Call (760) 241-7900", "tel:+17602417900"))
    ph = phs["content"]
    s = section(ph)
    g = grid(ph, s, 3, "soft")
    card(ph, g, "Victorville office", text="17177 & 17171 Yuma Street, Victorville, CA 92395",
         link_text="Get directions →", link_url="https://maps.google.com/?q=17177+Yuma+Street+Victorville+CA+92395")
    card(ph, g, "Phone", links="California (760) 241-7900|tel:+17602417900\nNevada (702) 508-7580|tel:+17025087580")
    card(ph, g, "Email and claims", links="info@isu-armac.com|mailto:info@isu-armac.com\nClaim contacts|/claim-contacts/\nPay online|https://isu-armac.epaypolicy.com/")
    s = section(ph, background="pale", compact=True)
    add_plugin(ph, "QuoteFormPlugin", L, target=s, form_type="contact", heading="Send us a message",
               intro="We'll get back to you within one business day.", button_text="Send Message", dark=False)


def build_thank_you(phs, wp=None, ctx=None):
    page_hero(phs["hero"], "Thank you", sub="We've received your request. A licensed agent will contact you within one business day.",
              primary=("Back to the homepage", "/"), secondary=("Call (760) 241-7900", "tel:+17602417900"))
    s = section(phs["content"], compact=True, heading="While you wait")
    g = grid(phs["content"], s, 3, "tile")
    card(phs["content"], g, "Read our blog", link_url="/blog/")
    card(phs["content"], g, "Meet the team", link_url="/our-team/")
    card(phs["content"], g, "Refer a friend", link_url="/refer-a-friend/")


def build_life_add(phs, wp=None, ctx=None):
    ph = phs["content"]
    add_plugin(ph, "TextPlugin", L, body=(
        "<p>Group life and accidental death and dismemberment (AD&amp;D) insurance give your employees and their families "
        "financial protection at a low cost per person. Most employers offer them together as part of a benefits package.</p>"
        "<h2>Group life insurance</h2>"
        "<p>Group term life pays a benefit to an employee's beneficiaries if the employee dies while covered. Employers often "
        "provide a flat amount or a multiple of salary, and many plans let employees buy additional coverage for themselves and "
        "their dependents through payroll deduction.</p>"
        "<h2>Accidental death and dismemberment</h2>"
        "<p>AD&amp;D pays an additional benefit if a covered employee dies or suffers a qualifying serious injury, such as the loss "
        "of a limb or eyesight, as the result of an accident. It is usually paired with group life and adds meaningful "
        "protection for a small added premium.</p>"
        "<h2>Why employers offer it</h2>"
        "<ul><li>Low cost per employee compared with individual policies</li>"
        "<li>Guaranteed coverage up to plan limits, often without medical questions</li>"
        "<li>A valued benefit that helps you recruit and keep good people</li>"
        "<li>Optional employee-paid coverage at no cost to the employer</li></ul>"
        "<h2>How ISU-ARMAC helps</h2>"
        "<p>We compare group life and AD&amp;D plans from multiple carriers, coordinate them with your medical, dental and "
        "vision benefits, and help your employees understand what they have. Ask us for a quote alongside your next benefits "
        "renewal.</p>"))
    faq = add_plugin(ph, "FAQPlugin", L)
    for i, (q, a) in enumerate([
        ("Is group life insurance portable if an employee leaves?", "Many group plans let employees convert or port their coverage when they leave. The terms depend on the carrier and plan, and we can explain the options in the plan you choose."),
        ("How much group life coverage should we offer?", "Common designs are a flat amount, such as $25,000 or $50,000, or a multiple of salary, such as one or two times annual earnings. We'll help you pick a design that fits your budget and workforce."),
        ("Can employees add coverage for their families?", "Yes. Most plans offer voluntary spouse and child life coverage that employees pay for through payroll deduction."),
    ]):
        add_plugin(ph, "FAQItemPlugin", L, target=faq, question=q, answer=a, open=(i == 0))


SPECS = {
    f"{IC}/life-accidental-death-dismemberment-insurance/": {"title": "Life & Accidental Death & Dismemberment Insurance",
                                                               "template": "detail.html", "build": build_life_add},
    "/": {"title": "Home", "template": "home.html", "build": build_home,
          "seo_title": "Insurance Agency in Victorville, CA | ISU-ARMAC Insurance Services"},
    f"{CI}/contractor-insurance/": {"title": "Contractor Insurance", "template": "landing.html", "build": build_contractor,
                                    "seo_title": "Contractor Insurance in CA, NV & AZ | ISU-ARMAC",
                                    "seo_description": "Contractor insurance, bonds and crew benefits from one agency. We shop 300+ carriers for contractors in California, Nevada and Arizona. Free comp review."},
    f"{CI}/hospital-insurance/": {"title": "Hospital Insurance & Benefits", "template": "landing.html", "build": build_hospital,
                                  "seo_title": "Hospital Insurance & Employee Benefits | ISU-ARMAC",
                                  "seo_description": "Property, casualty and employee benefits for independent hospitals, including self-insured plan management. One team, licensed nationwide."},
    "/industries/": {"title": "Industries", "template": "landing.html", "build": build_industries,
                     "seo_title": "Industries We Insure | ISU-ARMAC Insurance Services",
                     "seo_description": "Specialized business insurance for contractors, hospitals, medical and dental offices, restaurants, manufacturers, farms, nonprofits and more."},
    f"{PL}/": {"title": "Personal Insurance", "template": "landing.html",
               "build": hub_builder("Personal insurance", "Home, auto and everything in between, compared across 300+ carriers.", f"{PL}/", "Personal coverage", image="personal-family-home.jpg", alt="A family carrying groceries from their car to their desert home")},
    f"{PC}/": {"title": "Private Client Insurance", "template": "landing.html",
               "build": hub_builder("Private client insurance", "Tailored protection for significant homes, collections and assets.", f"{PC}/", "Private client coverage", image="private-client-desert-home.jpg", alt="A modern desert home with a pool at dusk")},
    f"{CI}/": {"title": "Business Insurance", "template": "landing.html",
               "build": hub_builder("Business insurance", "Liability, property, workers' comp and specialty coverage for every industry.", f"{CI}/", "Business coverage", image="business-bakery-owner.jpg", alt="A bakery owner hanging a sign in her shop window",
                                    extra_links=[("Hospitals", f"{CI}/hospital-insurance/")])},
    f"{IC}/employee-benefits/": {"title": "Employee Benefits", "template": "landing.html",
                                 "build": hub_builder("Employee benefits", "Group plans that help you hire, keep and care for your team.", f"{IC}/employee-benefits/", "Benefits we offer", image="benefits-team-meeting.jpg", alt="A team meeting in a bright office with mountain views",
                                                      extra_links=[("Group Medical", f"{IC}/group-medical/"), ("Group Dental", f"{IC}/group-dental/"),
                                                                   ("Group Vision", f"{IC}/group-vision-template/"), ("Group Life", f"{IC}/group-life/"),
                                                                   ("Life & AD&D", f"{IC}/life-accidental-death-dismemberment-insurance/"),
                                                                   ("Voluntary Benefits", f"{IC}/group-voluntary-benefits/")])},
    "/insurance-center/": {"title": "Insurance Center", "template": "landing.html",
                           "build": hub_builder("Insurance center", "Every type of coverage we offer, in one place.", "/insurance-center/", "Browse by category")},
    f"{IC}/": {"title": "Insurance Services", "template": "landing.html",
               "build": hub_builder("Insurance services", "Personal, private client, business and employee benefits coverage.", f"{IC}/", "Browse our services")},
    "/insurance-center/products/": {"title": "Insurance Products", "template": "landing.html",
                                    "build": hub_builder("Insurance products", "Health, Medicare and business insurance products.", "/insurance-center/products/", "Products")},
    "/our-team/": {"title": "Our Team", "template": "landing.html", "build": build_team},
    "/testimonials/": {"title": "Testimonials", "template": "landing.html", "build": build_testimonials},
    "/get-a-quote/": {"title": "Get a Quote", "template": "landing.html",
                      "build": form_page("Get a quote", "Tell us what you need. We'll compare 300+ carriers and come back with real options.", "general", "Request your quote", "Get My Quote")},
    "/business-insurance-quote/": {"title": "Business Insurance Quote", "template": "landing.html",
                                   "build": form_page("Business insurance quote", "Liability, property, workers' comp and more, compared across 300+ carriers.", "general", "Request your business quote", "Get My Quote")},
    "/get-a-group-benefits-quote/": {"title": "Get a Group Benefits Quote", "template": "landing.html",
                                     "build": form_page("Group benefits quote", "Medical, dental, vision, life and voluntary benefits for your team.", "benefits", "Request your benefits quote", "Get My Benefits Quote")},
    "/contact/": {"title": "Contact", "template": "landing.html", "build": build_contact},
    "/thank-you/": {"title": "Thank You", "template": "landing.html", "build": build_thank_you},
}
# Photos for industry pages converted from WordPress: shown in a page hero with the page title.
INDUSTRY_PHOTOS = {
    f"{CI}/medical-office-insurance/": ("industry-medical-office.jpg", "A receptionist and physician greeting a patient at a medical office front desk"),
    f"{CI}/dental-office-insurance/": ("industry-dental.jpg", "A dentist explaining an X-ray to a patient"),
    f"{CI}/restaurant-insurance/": ("industry-restaurant.jpg", "A chef plating a dish in a busy restaurant kitchen"),
    f"{CI}/manufacturer-insurance/": ("industry-manufacturer.jpg", "A machinist in safety glasses operating a CNC machine"),
    f"{CI}/property-manager-insurance/": ("industry-property-manager.jpg", "A property manager showing a tenant a renovated home"),
    f"{CI}/farm-insurance/": ("industry-farm.jpg", "A farmer checking irrigation lines in a field at sunrise"),
    f"{CI}/vacant-land-insurance/": ("industry-vacant-land.jpg", "Open desert land with a wire fence and mountains at sunset"),
    f"{CI}/non-profit-insurance/": ("industry-nonprofit.jpg", "Volunteers sorting donations at a community center"),
}


def industry_hero(placeholder, path, title):
    """Page hero with photo for a converted industry page; returns False when the page has no photo."""
    if path not in INDUSTRY_PHOTOS:
        return False
    image, alt = INDUSTRY_PHOTOS[path]
    page_hero(placeholder, title, sub="Coverage compared across 300+ carriers by a local, independent agency.",
              secondary=("Call (760) 241-7900", "tel:+17602417900"), image=PHOTO + image, alt=alt)
    return True


NEW_PAGES = [f"{CI}/hospital-insurance/", "/industries/"]


def spec_for(path):
    return SPECS.get(path, {})
