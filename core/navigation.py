"""Main menu. Each section: label, landing URL, and the links shown in its dropdown."""

IC = "/insurance-center/service"
PL = f"{IC}/personal-lines-insurance"
PC = f"{IC}/private-client-insurance"
CI = f"{IC}/commercial-insurance"

MAIN_MENU = [
    {
        "label": "Personal",
        "url": f"{PL}/",
        "links": [
            ("Auto", f"{PL}/auto-insurance/"),
            ("Classic Auto", f"{PL}/classic-auto-insurance/"),
            ("Home", f"{PL}/home-insurance/"),
            ("Flood", f"{PL}/flood-insurance/"),
            ("Earthquake", f"{PL}/earthquake-insurance/"),
            ("Boat", f"{PL}/boat-insurance/"),
            ("Motorcycle", f"{PL}/motorcycle-insurance/"),
            ("Pet", f"{PL}/pet-insurance/"),
            ("Long-Term Care", f"{PL}/long-term-care-insurance/"),
            ("Individual Dental", f"{PL}/individual-dental/"),
            ("Short-Term Disability", f"{PL}/individual-short-term-disability/"),
        ],
    },
    {
        "label": "Private Client",
        "url": f"{PC}/",
        "links": [
            ("High Net Worth", f"{PC}/high-net-worth-insurance/"),
            ("Valuable Possessions", f"{PC}/valuable-possessions-insurance/"),
            ("Umbrella", f"{PC}/umbrella-insurance/"),
            ("Secondary Home", f"{PC}/secondary-home-insurance/"),
            ("High Fire Risk", f"{PC}/high-fire-risk-insurance/"),
            ("Renters", f"{PC}/renters-insurance/"),
            ("Golf Carts", f"{PC}/golf-carts-insurance/"),
            ("Individual Life", f"{PC}/individual-life-insurance/"),
            ("Individual Medical", f"{PC}/individual-medical-client/"),
            ("Annuities", f"{PC}/annuities-personal/"),
        ],
    },
    {
        "label": "Business",
        "url": f"{CI}/",
        "links": [
            ("Business Owners Policy", f"{CI}/business-owners-insurance/"),
            ("General Liability", f"{CI}/general-liability-insurance/"),
            ("Business Auto", f"{CI}/business-auto-insurance/"),
            ("Commercial Property", f"{CI}/commercial-property-insurance/"),
            ("Workers' Compensation", f"{CI}/workers-compensation-insurance/"),
            ("Commercial Umbrella", f"{CI}/commercial-umbrella-insurance/"),
            ("Cyber Liability", f"{CI}/cyber-liability-insurance/"),
            ("Directors & Officers", f"{CI}/directors-and-officers-liability-insurance/"),
            ("Employment Practices", f"{CI}/employment-practice-liability-insurance/"),
            ("Errors & Omissions", f"{CI}/errors-omissions-liability/"),
            ("Crime", f"{CI}/crime-insurance/"),
            ("Inland Marine", f"{CI}/inland-marine-insurance/"),
            ("Environmental", f"{CI}/environmental-insurance/"),
            ("Key Person Life", f"{CI}/key-man-life-insurance/"),
            ("Surety Bonds", f"{CI}/surety-bonds/"),
            ("Vacant Land", f"{CI}/vacant-land-insurance/"),
        ],
    },
    {
        "label": "Employee Benefits",
        "url": f"{IC}/employee-benefits/",
        "links": [
            ("Group Medical", f"{IC}/group-medical/"),
            ("Group Dental", f"{IC}/group-dental/"),
            ("Group Vision", f"{IC}/group-vision-template/"),
            ("Group Life", f"{IC}/group-life/"),
            ("Life & AD&D", f"{IC}/life-accidental-death-dismemberment-insurance/"),
            ("Voluntary Benefits", f"{IC}/group-voluntary-benefits/"),
            ("401(k)", f"{IC}/employee-benefits/401k/"),
            ("Get a Group Benefits Quote", "/get-a-group-benefits-quote/"),
        ],
    },
    {
        "label": "Industries",
        "url": "/industries/",
        "links": [
            ("Contractors", f"{CI}/contractor-insurance/"),
            ("Hospitals", f"{CI}/hospital-insurance/"),
            ("Medical Office", f"{CI}/medical-office-insurance/"),
            ("Dental Office", f"{CI}/dental-office-insurance/"),
            ("Restaurants", f"{CI}/restaurant-insurance/"),
            ("Hospitality", f"{CI}/hospitality-insurance/"),
            ("Manufacturers", f"{CI}/manufacturer-insurance/"),
            ("Property Managers", f"{CI}/property-manager-insurance/"),
            ("Non-Profits", f"{CI}/non-profit-insurance/"),
            ("Farms", f"{CI}/farm-insurance/"),
            ("All industries", "/industries/"),
        ],
    },
    {
        "label": "About",
        "url": "/about-us/",
        "links": [
            ("About Us", "/about-us/"),
            ("Our Team", "/our-team/"),
            ("Testimonials", "/testimonials/"),
            ("Carriers", "/carriers/"),
            ("Partners", "/partners/"),
            ("Join Our Team", "/join-our-team/"),
            ("Contact", "/contact/"),
        ],
    },
    {
        "label": "Resources",
        "url": "/blog/",
        "links": [
            ("Blog", "/blog/"),
            ("Health & Medicare", "/insurance-center/products/health-insurance/"),
            ("Annuities", "/annuities/"),
            ("Glossary", f"{IC}/glossary/"),
            ("Claim Contacts", "/claim-contacts/"),
            ("Pay Online", "https://isu-armac.epaypolicy.com/"),
            ("Refer a Friend", "/refer-a-friend/"),
            ("Review Us", "/review-us/"),
        ],
    },
]

FOOTER_COLUMNS = [
    ("Insurance", [("Personal", f"{PL}/"), ("Private Client", f"{PC}/"), ("Business", f"{CI}/"),
                   ("Industries", "/industries/"), ("Health & Medicare", "/insurance-center/products/health-insurance/"),
                   ("Annuities", "/annuities/")]),
    ("Benefits", [("Employee Benefits", f"{IC}/employee-benefits/"), ("Group Medical", f"{IC}/group-medical/"),
                  ("Group Dental", f"{IC}/group-dental/"), ("Group Life", f"{IC}/group-life/"),
                  ("401(k)", f"{IC}/employee-benefits/401k/")]),
    ("Company", [("About Us", "/about-us/"), ("Our Team", "/our-team/"), ("Testimonials", "/testimonials/"),
                 ("Carriers", "/carriers/"), ("Partners", "/partners/"), ("Join Our Team", "/join-our-team/")]),
    ("Resources", [("Blog", "/blog/"), ("Glossary", f"{IC}/glossary/"), ("Claim Contacts", "/claim-contacts/"),
                   ("Pay Online", "https://isu-armac.epaypolicy.com/"), ("Refer a Friend", "/refer-a-friend/"),
                   ("Review Us", "/review-us/")]),
]

LEGAL_LINKS = [
    ("Privacy Policy", "/privacy-policy/"),
    ("Terms of Use", "/terms-use/"),
    ("CCPA Disclosure", "/ca-consumer-privacy-act-ccpa-disclosure/"),
    ("Site Map", "/site-map/"),
]

SITE_INFO = {
    "name": "ISU-ARMAC Insurance Services",
    "address_lines": ["17177 & 17171 Yuma Street", "Victorville, CA 92395"],
    "phone_ca": "(760) 241-7900",
    "phone_ca_tel": "+17602417900",
    "phone_nv": "(702) 508-7580",
    "phone_nv_tel": "+17025087580",
    "email": "info@isu-armac.com",
    "pay_online": "https://isu-armac.epaypolicy.com/",
}
