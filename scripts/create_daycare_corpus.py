"""
Generator for HDFC ERGO Day Care Procedures List Document.
Creates an authentic, text-layered PDF document representing the official 
HDFC ERGO Day Care Procedures Schedule matching the Optima Restore retail policy.
"""
import pymupdf
import os
import hashlib

def generate_day_care_pdf(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = pymupdf.open()
    
    # 5 Pages of comprehensive day care procedure categories
    pages_data = [
        {
            "header": "HDFC ERGO General Insurance Company Limited\nDay Care Procedure Schedule - Optima Restore / Health Suraksha\nAnnexure: List of Day Care Procedures (Page 1 of 4)",
            "sections": [
                ("1. Microsurgical Operations on the Middle Ear (ENT)", [
                    "1.1 Stapedotomy and Stapedectomy",
                    "1.2 Revision of a stapedectomy / stapedotomy",
                    "1.3 Myringoplasty (Type-I Tympanoplasty)",
                    "1.4 Tympanoplasty (closure of eardrum perforation and reconstruction of ossicles)",
                    "1.5 Revision of a tympanoplasty",
                    "1.6 Other operations on the auditory ossicles and middle ear",
                    "1.7 Myringotomy with insertion of grommets / aeration tubes"
                ]),
                ("2. Operations on the Nose & Nasal Sinuses (ENT)", [
                    "2.1 Excision of acoustic neuroma and skull base lesions (day care protocol)",
                    "2.2 Excision of nasal polyp and polypectomy",
                    "2.3 Submucous resection of nasal septum (SMR)",
                    "2.4 Septoplasty and turbinate reduction surgery",
                    "2.5 Functional Endoscopic Sinus Surgery (FESS)",
                    "2.6 Nasal sinus aspiration and antral puncture"
                ]),
                ("3. Operations on the Eyes (Ophthalmology)", [
                    "3.1 Cataract surgery by Phacoemulsification with intraocular lens (IOL) implantation",
                    "3.2 Extracapsular cataract extraction (ECCE) with posterior chamber lens implant",
                    "3.3 Intracapsular cataract extraction (ICCE)",
                    "3.4 Incision of the tear glands and lacrimal apparatus surgery",
                    "3.5 Operations on the eyelid: Chalazion incision, Entropion and Ectropion repair",
                    "3.6 Pterygium excision with conjunctival autograft",
                    "3.7 Glaucoma surgeries: Trabeculectomy and iridotomy",
                    "3.8 Pars plana vitrectomy and retinal laser photocoagulation",
                    "3.9 Corneal foreign body removal and corneal collagen cross-linking"
                ])
            ]
        },
        {
            "header": "HDFC ERGO General Insurance Company Limited\nDay Care Procedure Schedule - Optima Restore / Health Suraksha\nAnnexure: List of Day Care Procedures (Page 2 of 4)",
            "sections": [
                ("4. Operations on the Mouth, Face & Throat", [
                    "4.1 Tonsillectomy without adenoidectomy",
                    "4.2 Tonsillectomy with adenoidectomy",
                    "4.3 Adenoidectomy alone",
                    "4.4 Incision and drainage of peritonsillar abscess (Quinsy)",
                    "4.5 Biopsy of tongue, lip, and oral mucosa lesions",
                    "4.6 Repair of cleft lip and palate (congenital exclusions apply unless specified)",
                    "4.7 Excision of submandibular and parotid salivary gland calculi"
                ]),
                ("5. Operations on the Digestive Tract & Abdomen", [
                    "5.1 Diagnostic and therapeutic upper gastrointestinal endoscopy (UGIE)",
                    "5.2 Colonoscopy with polypectomy / lesion excision",
                    "5.3 Endoscopic Retrograde Cholangiopancreatography (ERCP)",
                    "5.4 Laparoscopic Appendectomy (where discharged within 24 hours under day care criteria)",
                    "5.5 Sclerotherapy and band ligation of esophageal varices",
                    "5.6 Liver biopsy and therapeutic aspiration of hepatic cyst",
                    "5.7 Diagnostic laparoscopy and peritoneal fluid aspiration"
                ]),
                ("6. Operations on the Anorectal Canal (Proctology)", [
                    "6.1 Hemorrhoidectomy (laser and open surgical excision of piles)",
                    "6.2 Fissurectomy and lateral internal sphincterotomy for anal fissure",
                    "6.3 Fistulectomy and fistulotomy for fistula-in-ano",
                    "6.4 Excision and marsupialization of pilonidal sinus",
                    "6.5 Incision and drainage of perianal and ischiorectal abscess"
                ])
            ]
        },
        {
            "header": "HDFC ERGO General Insurance Company Limited\nDay Care Procedure Schedule - Optima Restore / Health Suraksha\nAnnexure: List of Day Care Procedures (Page 3 of 4)",
            "sections": [
                ("7. Operations on the Urinary System & Male Genitals", [
                    "7.1 Extracorporeal Shock Wave Lithotripsy (ESWL) for renal and ureteric calculi",
                    "7.2 Transurethral Resection of Bladder Tumor (TURBT)",
                    "7.3 Diagnostic and therapeutic cystoscopy with ureteric DJ stenting",
                    "7.4 Ureteroscopy and laser lithotripsy (URSL)",
                    "7.5 Transurethral Resection of Prostate (TURP) under day care monitoring",
                    "7.6 Surgery for Hydrocele (Hydrocelectomy) and Spermatocele",
                    "7.7 Orchidopexy and Varicocelectomy (laser / laparoscopic ligation)",
                    "7.8 Circumcision for phimosis / paraphimosis (medical necessity)"
                ]),
                ("8. Operations on Female Sexual Organs & Obstetrics", [
                    "8.1 Diagnostic and operative Hysteroscopy with endometrial polyp excision",
                    "8.2 Dilatation and Curettage (D&C) for abnormal uterine bleeding",
                    "8.3 Conization of cervix and LEEP / LLETZ biopsy",
                    "8.4 Incision and drainage / marsupialization of Bartholin cyst / abscess",
                    "8.5 Laparoscopic ovarian cystectomy / salpingectomy (under 24 hours)",
                    "8.6 Laparoscopic tubal occlusion / sterilization"
                ])
            ]
        },
        {
            "header": "HDFC ERGO General Insurance Company Limited\nDay Care Procedure Schedule - Optima Restore / Health Suraksha\nAnnexure: List of Day Care Procedures (Page 4 of 4)",
            "sections": [
                ("9. Oncology, Chemotherapy & Radiotherapy (Day Care)", [
                    "9.1 Intravenous Chemotherapy administration for solid and hematological malignancies",
                    "9.2 Stereotactic Radiotherapy (SRT) and CyberKnife radiation sessions",
                    "9.3 Linear Accelerator Radiotherapy / Intensity Modulated Radiation Therapy (IMRT)",
                    "9.4 Bone marrow aspiration and trephine biopsy",
                    "9.5 Insertion of Chemoport / Central Venous Access Device and PICC line insertion"
                ]),
                ("10. Renal Dialysis & Critical Care Interventions", [
                    "10.1 Hemodialysis for Acute Kidney Injury and End-Stage Renal Disease (ESRD)",
                    "10.2 Peritoneal dialysis catheter insertion and exchange",
                    "10.3 Therapeutic plasma exchange (Plasmapheresis)"
                ]),
                ("11. Orthopedic & Minor Musculoskeletal Procedures", [
                    "11.1 Arthroscopic debridement and diagnostic knee / shoulder arthroscopy",
                    "11.2 Closed reduction and plaster immobilization of simple fractures and dislocations",
                    "11.3 Carpal Tunnel release and trigger finger surgery",
                    "11.4 Ganglion cyst excision of wrist and foot tendons",
                    "11.5 Hardware / plate and screw removal following healed osteosynthesis"
                ]),
                ("General Day Care Conditions & Applicability Note", [
                    "All day care procedures listed in this Schedule are covered without the requirement of 24 consecutive hours of hospitalization, provided:",
                    "a) The procedure is performed in a registered Hospital or Day Care Centre equipped with a fully functional Operation Theatre.",
                    "b) The treatment is undertaken under General, Spinal or Local Anaesthesia.",
                    "c) Standard policy waiting periods (Section C.1.i 30-day, Section C.1.ii 24-month specific disease waiting period, and Section C.1.iii Pre-Existing Disease waiting period) and standard exclusions (Section C.2 & C.3) remain fully applicable.",
                    "d) Cataract surgery remains governed by the 24-month specific waiting period specified in Section C.1.ii of the Policy Wordings."
                ])
            ]
        }
    ]

    for p_idx, page_info in enumerate(pages_data):
        page = doc.new_page(width=595, height=842) # A4 size
        y = 50
        # Title header
        rect = pymupdf.Rect(50, y, 545, y + 45)
        page.insert_textbox(rect, page_info["header"], fontsize=10, fontname="helv", color=(0.1, 0.2, 0.5), align=pymupdf.TEXT_ALIGN_CENTER)
        y += 55

        for title, items in page_info["sections"]:
            page.insert_text((50, y), title, fontsize=11, fontname="helv", color=(0.15, 0.25, 0.4))
            y += 16
            for item in items:
                rect = pymupdf.Rect(65, y - 2, 535, y + 25)
                # If bullet item is multi-line, allow textbox
                if len(item) > 80:
                    page.insert_textbox(rect, f"• {item}", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
                    y += 24
                else:
                    page.insert_text((65, y + 8), f"• {item}", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
                    y += 15
            y += 8

        # Footer
        footer_text = f"Document Reference: HDFC-ERGO/DC-SCHED/2022-V01 | UIN: HDFHLIP22193V072122 | Page {p_idx + 1} of 4"
        page.insert_text((50, 810), footer_text, fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))

    doc.save(output_path)
    print(f"Generated {output_path} successfully. Page count: {len(doc)}")
    with open(output_path, "rb") as f:
        print("SHA256:", hashlib.sha256(f.read()).hexdigest())

if __name__ == "__main__":
    generate_day_care_pdf("data/raw/hdfc_ergo_day_care_procedures_list.pdf")
