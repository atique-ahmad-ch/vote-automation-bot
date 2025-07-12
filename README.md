# Voting Bot API 
```
cd app
```
## Requirements File (requirements.txt)

```txt
Flask==2.3.3
Flask-CORS==4.0.0
selenium==4.15.0
undetected-chromedriver==3.5.4
Faker==19.12.0
schedule==1.2.0
```

## Server Setup Instructions

### 1. Install Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip -y

# Install Chrome dependencies
sudo apt install -y wget gnupg2 software-properties-common
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable -y

# Install additional dependencies for headless Chrome
sudo apt install -y xvfb x11-utils
```

### Setup Project

# Install Python dependencies
pip install -r requirements.txt

### Run the API Server

```bash
# Development mode
python voting_bot_api.py

# Production mode with gunicorn
pip install gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 voting_bot_api:app
```

### 4. Using PM2 for Production (Recommended)

```bash
# Install PM2
npm install -g pm2

# Start the application
pm2 start voting_bot_api.py --name "voting-bot-api" --interpreter python3

# Save PM2 configuration
pm2 save
pm2 startup
```

## API Endpoints

### 1. Health Check
```
GET /api/health
```

### 2. Start Bot
```
POST /api/start
Content-Type: application/json

{
  "interval_minutes": 30
}
```

### 3. Stop Bot
```
POST /api/stop
```

### 4. Get Status
```
GET /api/status
```

### 5. Single Vote
```
POST /api/vote-once
```

### 6. Get Sites
```
GET /api/sites
```

### 7. Get Logs
```
GET /api/logs
```

## Postman Collection Examples

### 1. Start Bot Request
```json
{
  "method": "POST",
  "url": "http://your-server-ip:5000/api/start",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "interval_minutes": 30
  }
}
```

### 2. Check Status Request
```json
{
  "method": "GET",
  "url": "http://your-server-ip:5000/api/status"
}
```

### 3. Stop Bot Request
```json
{
  "method": "POST",
  "url": "http://your-server-ip:5000/api/stop"
}
```

### 4. Execute Single Vote
```json
{
  "method": "POST",
  "url": "http://your-server-ip:5000/api/vote-once"
}
```