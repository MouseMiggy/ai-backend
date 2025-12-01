# AgriLink AI Validation Backend

Flask API for content moderation using OpenAI GPT-4.

## Railway Deployment

This app is configured to deploy on Railway.app.

### Setup Instructions:

1. **Create a Railway account** at https://railway.app

2. **Create a new project** in Railway

3. **Connect your GitHub repository** or deploy from the `ai-validation-backend` directory

4. **Set Environment Variables** in Railway:
   - `OPENAI_API_KEY`: Your OpenAI API key (required)
   - `PORT`: Railway will set this automatically

5. **Deploy**: Railway will automatically detect the Python app and deploy it

### Endpoints:

- `POST /validate-report` - Validate post reports
- `POST /validate-listing-report` - Validate listing reports  
- `POST /validate-comment-report` - Validate comment reports
- `POST /validate-message-report` - Validate message reports
- `GET /health` - Health check endpoint

### Local Development:

```bash
cd ai-validation-backend
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
python app.py
```

The app will run on http://localhost:5000

