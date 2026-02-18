import requests
from bs4 import BeautifulSoup
import os
import time
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/ejolie-openclaw-agent/.env')

session = requests.Session()
session.headers.update(
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'})
BASE = "https://www.ejolie.ro"

# LOGIN
print("=== LOGIN ===")
resp = session.post(f"{BASE}/manager/login/autentificare", data={
    'utilizator': os.getenv('EXTENDED_EMAIL'),
    'parola': os.getenv('EXTENDED_PASSWORD'),
}, allow_redirects=True)
if 'dashboard' not in resp.url:
    print("LOGIN FAILED!")
    exit()
print("OK!\n")


def gen_text(name, color=None, material=None, category="ocazie", length=None, cut=None):
    cat_map = {
        "ocazie": ("evenimente speciale", "nunti, botezuri, gale si receptii", "un eveniment important"),
        "seara": ("serile elegante", "cocktailuri, gale, cine romantice si petreceri", "o seara speciala"),
        "lungi": ("ocaziile deosebite", "nunti, gale, banchet si evenimente formale", "un eveniment elegant"),
        "zi": ("zilele active", "birou, intalniri, iesiri in oras si brunch", "o zi speciala"),
    }
    ctx, events, moment = cat_map.get(category, cat_map["ocazie"])
    sections = []

    if color:
        color_desc = {
            "negre": ("negru", "sofisticata si misterioasa", "aurii sau argintii", "Negrul este culoarea elegantei absolute"),
            "rosii": ("rosu", "pasionala si indrazneata", "aurii sau negre", "Rosul este culoarea curajului si a feminitatii"),
            "verzi": ("verde", "proaspata si rafinata", "aurii sau nude", "Verdele simbolizeaza prospetimea si armonia"),
            "albastre": ("albastru", "regala si calma", "argintii sau albe", "Albastrul evoca eleganta regala si serenitate"),
            "roz": ("roz", "romantica si delicata", "argintii sau nude", "Rozul aduce un aer romantic si feminin"),
            "fucsia": ("fucsia", "vibranta si plina de energie", "negre sau argintii", "Fucsia este alegerea perfecta pentru cele care vor sa iasa in evidenta"),
            "albe": ("alb", "pura si luminoasa", "aurii sau roz", "Albul simbolizeaza puritatea si eleganta suprema"),
            "bordo": ("bordo", "nobila si sofisticata", "aurii sau negre", "Bordo este nuanta regala care emana rafinament"),
            "mov": ("mov", "mistica si eleganta", "argintii sau nude", "Movul combina misterul cu eleganta intr-un mod unic"),
            "aurii": ("auriu", "stralucitoare si festiva", "negre sau nude", "Auriul este sinonim cu stralucirea si luxul"),
            "crem": ("crem", "calda si sofisticata", "aurii sau nude", "Cremul ofera o eleganta subtila si atemporala"),
        }
        cname, adj, acc, intro = color_desc.get(
            color, (color, "eleganta", "complementare", "Aceasta nuanta este deosebita"))
        sections.append(
            f'<h2>Rochii {color.title()} - Eleganta {adj.split()[0].title()}</h2>\n<p>{intro}, iar rochiile {color} din colectia Ejolie sunt perfecte pentru {ctx}. Fie ca alegi un model lung din satin sau o rochie midi din dantela, vei arata impecabil la {events}.</p>')
        sections.append(
            f'<h2>Materiale si Modele Variate</h2>\n<p>Colectia noastra de rochii {color} include modele din satin cu luciu elegant, dantela pentru un look romantic, voal pentru o cadere gratioasa si tafta pentru structura. Fiecare rochie este creata cu atentie la detalii pentru a-ti oferi confort si un aspect rafinat la {moment}.</p>')
        sections.append(f'<h2>Cum Porti Rochiile {color.title()}</h2>\n<p>Completeaza tinuta cu accesorii {acc} pentru un contrast armonios. La Ejolie gasesti rochii {color} in toate lungimile si croielile, de la modele mulate si sexy pana la rochii evazate si romantice. Comanda online cu livrare rapida in toata Romania.</p>')
    elif material:
        mat_desc = {
            "satin": ("satin", "luciul subtil si caderea fluida", "Satinul este materialul regilor", "un luciu natural care capteaza lumina"),
            "dantela": ("dantela", "textura romantica si detaliile fine", "Dantela este sinonimul elegantei feminine", "un aspect romantic si sofisticat"),
            "voal": ("voal", "usurintea si transparenta delicata", "Voalul aduce un aer eteric", "o cadere naturala si gratioasa"),
            "tafta": ("tafta", "volumul si structura impecabila", "Tafta creeaza siluete dramatice", "un volum natural"),
            "organza": ("organza", "transparenta si rigiditatea eleganta", "Organza transforma orice rochie", "straturi de eleganta si volum"),
        }
        mname, quality, intro, detail = mat_desc.get(
            material, (material, "calitatea premium", "Un material deosebit", "un aspect unic"))
        sections.append(f'<h2>Rochii din {mname.title()} pentru {ctx.title()}</h2>\n<p>{intro} si rochiile din {mname} sunt alegerea ideala pentru {events}. Colectia Ejolie ofera modele variate din {mname}, fiecare cu {detail} care te va face sa te simti speciala.</p>')
        sections.append(f'<h2>De Ce Sa Alegi {mname.title()}</h2>\n<p>Rochiile din {mname} se remarca prin {quality}. Disponibile in nuante variate de la negru clasic la rosu pasional, de la albastru regal la roz romantic, rochiile noastre din {mname} sunt perfecte pentru orice {moment}.</p>')
        sections.append(
            f'<h2>Modele si Croieli</h2>\n<p>Alege dintre rochii lungi din {mname} pentru un look dramatic, rochii midi pentru versatilitate, sau modele mulate pentru un efect sexy. Toate rochiile Ejolie din {mname} vin cu livrare rapida si retururi gratuite.</p>')
    elif length:
        len_desc = {
            "lungi": ("lungi", "dramatice si impunatoare", "gale, nunti si evenimente formale"),
            "midi": ("midi", "versatile si moderne", "cocktailuri, nunti de zi si evenimente semi-formale"),
        }
        lname, adj, ev = len_desc.get(length, (length, "elegante", events))
        sections.append(f'<h2>Rochii {lname.title()} de {category.title()}</h2>\n<p>Rochiile {lname} sunt {adj}, perfecte pentru {ev}. Colectia Ejolie include modele din satin, dantela, voal si tafta, in culori variate de la negru clasic la rosu pasional.</p>')
        sections.append(
            f'<h2>Materiale si Culori Disponibile</h2>\n<p>Alege din gama noastra de rochii {lname} in nuante elegante: negru, rosu, albastru, verde, bordo sau auriu. Fiecare model este confectionat din materiale premium pentru confort si eleganta la {moment}.</p>')
        sections.append(f'<h2>Livrare Rapida in Romania</h2>\n<p>Comanda rochia perfecta de pe Ejolie.ro si beneficiezi de livrare rapida. Oferim o gama variata de croieli: mulate, evazate, in A, pentru a se potrivi oricarei siluete.</p>')
    elif cut:
        sections.append(
            f'<h2>Rochii {cut.title()} de {category.title()}</h2>\n<p>Rochiile {cut} sunt alegerea perfecta pentru {ctx}. Croiala pune in valoare silueta si ofera un look modern si sofisticat la {events}.</p>')
        sections.append(f'<h2>Culori si Materiale</h2>\n<p>Disponibile in nuante clasice si vibrante: negru, rosu, albastru, verde, si din materiale premium: satin, dantela, voal. Fiecare rochie Ejolie este creata pentru confort si eleganta.</p>')
        sections.append(f'<h2>Comanda Online</h2>\n<p>Alege rochia perfecta de pe Ejolie.ro cu livrare rapida in toata Romania. Colectia noastra include modele pentru toate evenimentele speciale.</p>')
    return "\n\n".join(sections)


pages = [
    {"nume": "Rochii rosii de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/rosu-21", "h1": "Rochii Rosii de Ocazie", "title": "Rochii Rosii de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii rosii de ocazie Ejolie. Modele elegante din satin, dantela si voal pentru nunti si evenimente. De la {PRET} lei cu livrare rapida!", "text_args": {"color": "rosii", "category": "ocazie"}},
    {"nume": "Rochii verzi de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/verde-23", "h1": "Rochii Verzi de Ocazie", "title": "Rochii Verzi de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii verzi de ocazie Ejolie. Modele rafinate din satin si dantela pentru evenimente speciale. De la {PRET} lei!", "text_args": {"color": "verzi", "category": "ocazie"}},
    {"nume": "Rochii albastre de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/albastru-22", "h1": "Rochii Albastre de Ocazie", "title": "Rochii Albastre de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii albastre de ocazie Ejolie. Nuante regale din satin si voal pentru nunti si gale. De la {PRET} lei!", "text_args": {"color": "albastre", "category": "ocazie"}},
    {"nume": "Rochii roz de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/roz-24", "h1": "Rochii Roz de Ocazie", "title": "Rochii Roz de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii roz de ocazie Ejolie. Modele romantice din satin si dantela pentru evenimente deosebite. De la {PRET} lei!", "text_args": {"color": "roz", "category": "ocazie"}},
    {"nume": "Rochii fucsia de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/fucsia-3053", "h1": "Rochii Fucsia de Ocazie", "title": "Rochii Fucsia de Ocazie | Vibrante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii fucsia de ocazie Ejolie. Modele vibrante si elegante pentru nunti si evenimente speciale. De la {PRET} lei!", "text_args": {"color": "fucsia", "category": "ocazie"}},
    {"nume": "Rochii albe de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/alb-19", "h1": "Rochii Albe de Ocazie", "title": "Rochii Albe de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii albe de ocazie Ejolie. Modele pure si elegante din satin si dantela. De la {PRET} lei!", "text_args": {"color": "albe", "category": "ocazie"}},
    {"nume": "Rochii bordo de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/bordo-27", "h1": "Rochii Bordo de Ocazie", "title": "Rochii Bordo de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii bordo de ocazie Ejolie. Modele sofisticate din satin si catifea pentru nunti si gale. De la {PRET} lei!", "text_args": {"color": "bordo", "category": "ocazie"}},
    {"nume": "Rochii mov de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/mov-25", "h1": "Rochii Mov de Ocazie", "title": "Rochii Mov de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii mov de ocazie Ejolie. Modele mistice si elegante din satin si voal. De la {PRET} lei!", "text_args": {"color": "mov", "category": "ocazie"}},
    {"nume": "Rochii aurii de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/auriu-26", "h1": "Rochii Aurii de Ocazie", "title": "Rochii Aurii de Ocazie | Stralucitoare de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii aurii de ocazie Ejolie. Modele stralucitoare si festive pentru nunti si gale. De la {PRET} lei!", "text_args": {"color": "aurii", "category": "ocazie"}},
    {"nume": "Rochii din satin de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/material/satin-3079", "h1": "Rochii din Satin de Ocazie", "title": "Rochii din Satin de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii din satin de ocazie Ejolie. Luciu elegant si cadere fluida pentru nunti si evenimente. De la {PRET} lei!", "text_args": {"material": "satin", "category": "ocazie"}},
    {"nume": "Rochii din dantela de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/material/dantela-7455", "h1": "Rochii din Dantela de Ocazie", "title": "Rochii din Dantela de Ocazie | Romantice de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii din dantela de ocazie Ejolie. Modele romantice cu detalii fine pentru nunti si gale. De la {PRET} lei!", "text_args": {"material": "dantela", "category": "ocazie"}},
    {"nume": "Rochii din voal de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/material/voal-44", "h1": "Rochii din Voal de Ocazie", "title": "Rochii din Voal de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii din voal de ocazie Ejolie. Modele eterice cu cadere gratiosa pentru evenimente. De la {PRET} lei!", "text_args": {"material": "voal", "category": "ocazie"}},
    {"nume": "Rochii din tafta de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/material/tafta-43", "h1": "Rochii din Tafta de Ocazie", "title": "Rochii din Tafta de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii din tafta de ocazie Ejolie. Modele cu volum si structura pentru nunti si gale. De la {PRET} lei!", "text_args": {"material": "tafta", "category": "ocazie"}},
    {"nume": "Rochii din organza de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/material/organza-7456", "h1": "Rochii din Organza de Ocazie", "title": "Rochii din Organza de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii din organza de ocazie Ejolie. Modele elegante cu transparenta delicata. De la {PRET} lei!", "text_args": {"material": "organza", "category": "ocazie"}},
    {"nume": "Rochii lungi de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/lungime/lungi-51", "h1": "Rochii Lungi de Ocazie", "title": "Rochii Lungi de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii lungi de ocazie Ejolie. Modele dramatice din satin, dantela si voal. De la {PRET} lei!", "text_args": {"length": "lungi", "category": "ocazie"}},
    {"nume": "Rochii midi de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/lungime/medii-53", "h1": "Rochii Midi de Ocazie", "title": "Rochii Midi de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii midi de ocazie Ejolie. Modele versatile si moderne pentru nunti si evenimente. De la {PRET} lei!", "text_args": {"length": "midi", "category": "ocazie"}},
    {"nume": "Rochii mulate de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/croi/mulat-57", "h1": "Rochii Mulate de Ocazie", "title": "Rochii Mulate de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii mulate de ocazie Ejolie. Modele sexy si sofisticate care pun in valoare silueta. De la {PRET} lei!", "text_args": {"cut": "mulate", "category": "ocazie"}},
    {"nume": "Rochii negre de seara", "link": "https://ejolie.ro/catalog/rochii/rochii-de-seara/filtru/culoare/negru-20", "h1": "Rochii Negre de Seara", "title": "Rochii Negre de Seara | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii negre de seara Ejolie. Modele sofisticate din satin si dantela pentru cocktailuri si gale. De la {PRET} lei!", "text_args": {"color": "negre", "category": "seara"}},
    {"nume": "Rochii rosii de seara", "link": "https://ejolie.ro/catalog/rochii/rochii-de-seara/filtru/culoare/rosu-21", "h1": "Rochii Rosii de Seara", "title": "Rochii Rosii de Seara | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii rosii de seara Ejolie. Modele pasionale si indraznete pentru seri speciale. De la {PRET} lei!", "text_args": {"color": "rosii", "category": "seara"}},
    {"nume": "Rochii albastre de seara", "link": "https://ejolie.ro/catalog/rochii/rochii-de-seara/filtru/culoare/albastru-22", "h1": "Rochii Albastre de Seara", "title": "Rochii Albastre de Seara | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii albastre de seara Ejolie. Nuante regale din satin si voal pentru cocktailuri si gale. De la {PRET} lei!", "text_args": {"color": "albastre", "category": "seara"}},
    {"nume": "Rochii verzi de seara", "link": "https://ejolie.ro/catalog/rochii/rochii-de-seara/filtru/culoare/verde-23", "h1": "Rochii Verzi de Seara", "title": "Rochii Verzi de Seara | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii verzi de seara Ejolie. Modele rafinate si proaspete pentru seri elegante. De la {PRET} lei!", "text_args": {"color": "verzi", "category": "seara"}},
    {"nume": "Rochii negre lungi", "link": "https://ejolie.ro/catalog/rochii/rochii-lungi/filtru/culoare/negru-20", "h1": "Rochii Negre Lungi", "title": "Rochii Negre Lungi | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii negre lungi Ejolie. Modele dramatice si impunatoare din satin si dantela. De la {PRET} lei!", "text_args": {"color": "negre", "category": "lungi"}},
    {"nume": "Rochii rosii lungi", "link": "https://ejolie.ro/catalog/rochii/rochii-lungi/filtru/culoare/rosu-21", "h1": "Rochii Rosii Lungi", "title": "Rochii Rosii Lungi | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii rosii lungi Ejolie. Modele pasionale si dramatice pentru evenimente speciale. De la {PRET} lei!", "text_args": {"color": "rosii", "category": "lungi"}},
    {"nume": "Rochii lungi din satin", "link": "https://ejolie.ro/catalog/rochii/rochii-lungi/filtru/material/satin-3079", "h1": "Rochii Lungi din Satin", "title": "Rochii Lungi din Satin | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii lungi din satin Ejolie. Luciu elegant si cadere fluida pentru nunti si gale. De la {PRET} lei!", "text_args": {"material": "satin", "category": "lungi"}},
    {"nume": "Rochii negre de zi", "link": "https://ejolie.ro/catalog/rochii/rochii-de-zi/filtru/culoare/negru-20", "h1": "Rochii Negre de Zi", "title": "Rochii Negre de Zi | Casual Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii negre de zi Ejolie. Modele casual-elegante pentru birou si iesiri in oras. De la {PRET} lei!", "text_args": {"color": "negre", "category": "zi"}},
    {"nume": "Rochii rosii de zi", "link": "https://ejolie.ro/catalog/rochii/rochii-de-zi/filtru/culoare/rosu-21", "h1": "Rochii Rosii de Zi", "title": "Rochii Rosii de Zi | Vibrante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii rosii de zi Ejolie. Modele vibrante si feminine pentru zilele active. De la {PRET} lei!", "text_args": {"color": "rosii", "category": "zi"}},
    {"nume": "Rochii de seara din satin", "link": "https://ejolie.ro/catalog/rochii/rochii-de-seara/filtru/material/satin-3079", "h1": "Rochii de Seara din Satin", "title": "Rochii de Seara din Satin | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii de seara din satin Ejolie. Luciu sofisticat pentru cocktailuri si gale. De la {PRET} lei!", "text_args": {"material": "satin", "category": "seara"}},
    {"nume": "Rochii de seara din dantela", "link": "https://ejolie.ro/catalog/rochii/rochii-de-seara/filtru/material/dantela-7455", "h1": "Rochii de Seara din Dantela", "title": "Rochii de Seara din Dantela | Romantice de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii de seara din dantela Ejolie. Modele romantice cu detalii fine pentru seri speciale. De la {PRET} lei!", "text_args": {"material": "dantela", "category": "seara"}},
    {"nume": "Rochii crem de ocazie", "link": "https://ejolie.ro/catalog/rochii/rochii-de-ocazie/filtru/culoare/crem-3051", "h1": "Rochii Crem de Ocazie", "title": "Rochii Crem de Ocazie | Elegante de la {PRET} lei | Ejolie.ro",
        "desc": "Rochii crem de ocazie Ejolie. Modele sofisticate si calde pentru nunti si evenimente. De la {PRET} lei!", "text_args": {"color": "crem", "category": "ocazie"}},
]

print(f"=== CREATING {len(pages)} SEO PAGES ===\n")
success = 0
failed = []

for i, page in enumerate(pages, 1):
    seo_text = gen_text(page["nume"], **page["text_args"])
    data = {
        'trimite': 'value',
        'camp_nume': page["nume"],
        'camp_link': page["link"],
        'camp_nume_h1': page["h1"],
        'camp_seotitle': page["title"],
        'camp_seodescription': page["desc"],
        'camp_robots': '',
        'camp_continut': seo_text,
    }
    resp = session.post(
        f"{BASE}/manager/seo_link_filtru/adauga", data=data, allow_redirects=True)
    if resp.status_code == 200:
        success += 1
        print(f"  OK {i}/{len(pages)}: {page['nume']}")
    else:
        failed.append(page['nume'])
        print(f"  FAIL {i}/{len(pages)}: {page['nume']} -> {resp.status_code}")
    time.sleep(0.5)

print(f"\n=== RESULTS ===")
print(f"Success: {success}/{len(pages)}")
if failed:
    print(f"Failed: {failed}")

print(f"\n=== VERIFICATION ===")
resp_list = session.get(f"{BASE}/manager/seo_link_filtru")
soup = BeautifulSoup(resp_list.text, 'html.parser')
entries = [a for a in soup.find_all(
    'a', href=True) if 'seo_link_filtru/modifica' in a['href']]
print(f"Total entries in admin: {len(entries)}")
