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
