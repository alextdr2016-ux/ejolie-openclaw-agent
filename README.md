# 🦞 Ejolie OpenClaw Agent

AI-powered sales and inventory reporting system for ejolie.ro e-commerce platform.

## 📋 Features

- 📊 **Sales Reports** - Custom period analysis with detailed metrics
- 📦 **Stock Monitoring** - Real-time inventory tracking and alerts
- 💰 **Profit Analysis** - Margin calculations and profitability insights
- 🛒 **Order Management** - Pending orders tracking
- 💬 **WhatsApp Integration** - Receive reports directly on WhatsApp

## 🏗️ Architecture

```
WhatsApp → OpenClaw (EC2) → Python Scripts → Extended API → ejolie.ro
```

## 🚀 Quick Start

### Prerequisites

- Node.js 22+
- Python 3.10+
- AWS EC2 instance (Ubuntu 22.04)
- OpenAI API key
- ejolie.ro Extended API key

### Local Development

1. Clone the repository:

```bash
git clone https://github.com/alextdr2016-ux/ejolie-openclaw-agent.git
cd ejolie-openclaw-agent
```

2. Setup environment:

```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Install Python dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

4. Install OpenClaw:

```bash
npm install -g openclaw@latest
openclaw onboard
```

### Deployment to EC2

See [INSTALLATION.md](docs/INSTALLATION.md) for detailed deployment instructions.

## 📖 Usage

### Generate Sales Report

Send to WhatsApp:

```
Raport vânzări de la 01-01-2024 până la 31-01-2024
```

### Check Low Stock

Send to WhatsApp:

```
Stoc critic
```

See [USAGE.md](docs/USAGE.md) for all available commands.

## 🔒 Security

- Never commit `.env` or API keys
- Use AWS IAM roles for EC2 permissions
- Restrict OpenClaw access with phone number whitelist
- Keep dependencies updated

## 🛠️ Tech Stack

- **OpenClaw** - AI agent gateway
- **OpenAI GPT-4** - Language model
- **Python 3.10** - Backend scripts
- **Extended API** - E-commerce data source
- **AWS EC2** - Hosting
- **Git/GitHub** - Version control

## 📚 Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [API Documentation](docs/API_DOCUMENTATION.md)
- [Usage Guide](docs/USAGE.md)

## 👨‍💻 Author

**Alex** - Cloud Engineer in Training

- GitHub: [@alextdr2016-ux](https://github.com/alextdr2016-ux)
- LinkedIn: [Your LinkedIn]

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- OpenClaw community
- Extended e-commerce platform
- AWS learning resources

# 🦞 Ejolie.ro OpenClaw Agent

AI-powered business assistant for [ejolie.ro](https://ejolie.ro) — Romanian fashion e-commerce store. Built on [OpenClaw](https://openclaw.ai) with GPT-5.

## 🚀 Features

### 📊 Sales Reports

Generate detailed sales reports via WhatsApp/Telegram with support for multiple report types, time periods, and brand filters.

**Report types:** `vanzari` (all orders) | `incasate` (paid) | `returnate` (returns) | `produse` (product breakdown) | `profit` (profit analysis with purchase costs)

**Periods:** `azi` | `ieri` | `luna asta` | `luna trecuta` | month names | custom date ranges (`de la DD-MM-YYYY pana la DD-MM-YYYY`)

**Brand filter:** `trendya` | `ejolie` | `artista`

```bash
# Examples (send on Telegram/WhatsApp)
raport vanzari azi
raport profit luna trecuta
raport incasate ianuarie brand trendya
raport vanzari de la 06-02-2026 pana la 08-02-2026
```

### 📑 Excel Export

Generate and auto-send `.xlsx` reports with 3 sheets: Comenzi (orders), Produse (product details), Sumar (summary with KPIs, brand breakdown, top 20 products).

```bash
raport excel luna trecuta
raport excel decembrie 2025
raport excel ianuarie brand ejolie
```

### 🔍 Product Search

Search 681+ products with images, prices, stock status, and direct links. Images sent inline on WhatsApp/Telegram.

```bash
arată-mi rochii florence
vreau o rochie neagră
ce bluze aveți?
```

### 📝 SEO Tools

Audit product descriptions and generate SEO-optimized content (meta titles, descriptions, keywords, alt text).

```bash
audit seo
generează descriere seo pentru rochie florence
```

### 💬 Knowledge Base

Answers customer questions about store policies using scraped content from ejolie.ro (returns, exchanges, shipping, payments, contact, loyalty program).

```bash
care e politica de retur?
cum fac schimb de produs?
```

### 🖥️ Coding Assistant

Full coding capabilities via `openclaw chat` — read/write files, run commands, install packages, manage server.

---

## 📁 Project Structure

```
ejolie-openclaw-agent/
├── ejolie-sales/
│   ├── .env                    # API credentials
│   └── scripts/
│       ├── utils.py            # Core utilities (API, parsing, reports)
│       ├── sales_report.py     # Text report generator
│       ├── export_xlsx.py      # Excel report generator
│       ├── product_search.py   # Product search from feed
│       ├── product_seo.py      # SEO audit & content tool
│       ├── product_feed.json   # Product catalog (681 products)
│       └── cost_cache.json     # Purchase prices (5829 options)
```

### OpenClaw Workspace (`~/.openclaw/workspace/`)

```
├── SOUL.md                     # Bot identity & command reference
├── AGENTS.md                   # Detailed skill instructions
├── knowledge/
│   └── ejolie-info.txt         # Store policies & info
└── skills/
    └── ejolie-sales/ → symlink to repo
```

---

## ⚙️ Setup

### Prerequisites

- Ubuntu 24 EC2 instance
- Node.js 22+
- Python 3.12+
- OpenClaw installed (`npm install -g openclaw`)
- OpenAI API key

### Installation

```bash
# Clone repo
git clone https://github.com/alextdr2016-ux/ejolie-openclaw-agent.git
cd ejolie-openclaw-agent

# Create .env
cat > ejolie-sales/.env << 'EOF'
EJOLIE_API_KEY=your_api_key_here
EJOLIE_API_URL=https://ejolie.ro/api/
EOF

# Install Python dependencies
pip3 install openpyxl --break-system-packages

# Symlink to OpenClaw workspace
mkdir -p ~/.openclaw/workspace/skills
ln -s $(pwd)/ejolie-sales ~/.openclaw/workspace/skills/ejolie-sales

# Copy workspace files
cp SOUL.md ~/.openclaw/workspace/SOUL.md
cp AGENTS.md ~/.openclaw/workspace/AGENTS.md
mkdir -p ~/.openclaw/workspace/knowledge
cp knowledge/ejolie-info.txt ~/.openclaw/workspace/knowledge/

# Configure OpenClaw
openclaw config set agents.defaults.model.primary "openai/gpt-5"
openclaw config set tools.profile "full"

# Connect Telegram
openclaw config set channels.telegram.enabled true
openclaw config set channels.telegram.botToken "your_telegram_bot_token"
openclaw config set channels.telegram.dmPolicy "pairing"

# Start
openclaw gateway restart
```

### Build Product Cache

```bash
# Download product feed
python3 -c "
import urllib.request, csv, json, io
url='https://ejolie.ro/continut/feed/fb_product.tsv'
req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
data=urllib.request.urlopen(req,timeout=30).read().decode('utf-8-sig')
reader=csv.DictReader(io.StringIO(data),delimiter='\t',quotechar='\"')
products=[{'id':r.get('id','').strip(),'title':r.get('title','').strip(),
'price':r.get('price','').strip(),'sale_price':r.get('sale_price','').strip(),
'image':r.get('image_link','').strip(),'link':r.get('link','').strip(),
'brand':r.get('brand','').strip(),'category':r.get('product_type','').strip(),
'available':r.get('availability','').strip(),
'description':r.get('description','').strip()[:200]} for r in reader]
with open('ejolie-sales/scripts/product_feed.json','w') as f: json.dump(products,f,ensure_ascii=False,indent=1)
print(f'{len(products)} produse salvate')
"

# Build cost cache (purchase prices from supplier API)
python3 ejolie-sales/scripts/build_cost_cache.py
```

---

## 🧪 Testing

### Direct Script Testing

```bash
# Sales report
python3 ejolie-sales/scripts/sales_report.py --type vanzari --period "azi"
python3 ejolie-sales/scripts/sales_report.py --type profit --period "luna trecuta" --brand "trendya"

# Excel export
python3 ejolie-sales/scripts/export_xlsx.py --period "decembrie"
python3 ejolie-sales/scripts/export_xlsx.py --period "luna trecuta" --brand "ejolie"

# Product search
python3 ejolie-sales/scripts/product_search.py --query "florence"
python3 ejolie-sales/scripts/product_search.py --query "rochie neagra" --limit 5

# SEO audit
python3 ejolie-sales/scripts/product_seo.py --action audit
python3 ejolie-sales/scripts/product_seo.py --action search --query "florence"
```

### OpenClaw Agent Testing

```bash
# Single message
openclaw agent --agent main --message "raport vanzari azi"

# Interactive chat
openclaw chat

# Send file manually
openclaw message send --channel telegram --target CHAT_ID --media /path/file.xlsx --message "Raport"
```

### Channel Status

```bash
openclaw channels status
openclaw gateway status
openclaw channels logs
```

---

## 📡 Channels

| Channel  | Status       | Usage                                        |
| -------- | ------------ | -------------------------------------------- |
| Telegram | ✅ Active    | @fabrexbot — reports, search, knowledge base |
| WhatsApp | ⚪ Available | Connect via `openclaw channels login`        |
| CLI      | ✅ Active    | `openclaw chat` — coding assistant           |

---

## 🔧 API Reference

### Extended API (ejolie.ro)

- **Orders:** `?comenzi&data_start=DD-MM-YYYY&data_end=DD-MM-YYYY&limit=2000&apikey=KEY`
- **Search:** `?search&cuvant=QUERY&apikey=KEY` (returns product IDs)
- **Products:** `?produse&id_produse=ID1,ID2&furnizor=true&apikey=KEY`
- **Suppliers:** `?furnizori&apikey=KEY`

### Product Feed

- **URL:** `https://ejolie.ro/continut/feed/fb_product.tsv`
- **Format:** TSV with columns: id, availability, condition, description, image_link, link, title, price, sale_price, brand, product_type

---

## 📋 Configuration

### Model Selection

```bash
openclaw config set agents.defaults.model.primary "openai/gpt-5"      # Best quality
openclaw config set agents.defaults.model.primary "openai/gpt-5-mini"  # Best value
```

### Tools Profile

```bash
openclaw config set tools.profile "full"     # Coding + messaging (recommended)
openclaw config set tools.profile "coding"   # Coding only (no message sending)
```

---

## 📄 License

Private project for ejolie.ro

## 👤 Author

Alex Tudor — [@alextdr2016-ux](https://github.com/alextdr2016-ux)
