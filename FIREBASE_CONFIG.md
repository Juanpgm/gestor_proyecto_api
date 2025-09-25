# Firebase Configuration Guide

## ⚡ Automatic Setup

The API now uses **functional programming** to automatically detect the environment and configure Firebase appropriately.

## 🏗️ Architecture

```
database/
├── firebase_config.py    # ✅ NEW: Functional auto-configuration
└── __init__.py
```

## 🔧 Configuration

### Local Development

```bash
# Use Application Default Credentials (ADC)
gcloud auth application-default login
```

### Railway Deployment

Set these environment variables in Railway Dashboard:

```
FIREBASE_PROJECT_ID=your-project-id
GOOGLE_CLOUD_PROJECT=your-project-id
FIREBASE_PRIVATE_KEY_ID=your-key-id
FIREBASE_PRIVATE_KEY=your-private-key
FIREBASE_CLIENT_EMAIL=service-account@project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
```

## 🚀 Features

- ✅ **Auto Environment Detection**: Detects Railway/Vercel/Heroku/Local automatically
- ✅ **Functional Programming**: Pure functions, no side effects
- ✅ **Lazy Initialization**: Firebase only initialized when needed
- ✅ **Error Handling**: Graceful degradation if Firebase unavailable
- ✅ **Security**: No hardcoded credentials
- ✅ **Caching**: LRU cache for performance

## 📊 Usage

```python
from database.firebase_config import FirebaseManager

# Check status
status = FirebaseManager.test_connection()
print(status['connected'])  # True/False

# Setup (automatic)
success = FirebaseManager.setup()

# Get client
client = FirebaseManager.get_client()
```

## 🔒 Security Notes

- Never commit service account keys
- Use environment variables for all credentials
- Rotate keys regularly
- Use least privilege IAM roles
