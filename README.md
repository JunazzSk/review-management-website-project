
# ReviewPilot

ReviewPilot is a Flask-based review management prototype that helps businesses manage customer reviews and reply drafts.

## Features

- User registration and login
- Business-specific review dashboard
- Customer review ratings and reply drafts
- Reply approval and change-request workflow
- Reply version history
- Recycle Bin with restore and permanent-delete options
- Automatic removal of expired deleted reply versions

## Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- SQLite
- HTML
- CSS

## Run Locally

1. Clone this repository.
2. Create and activate a Python virtual environment.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:

   ```bash
   python run.py
   ```

5. Open http://127.0.0.1:5000 in your browser.

## Project Status

This is a local prototype. Reviews and replies are not automatically imported from or published to Google Business Profile.

## Security

Configure a strong secret key using the `REVIEWPILOT_SECRET_KEY` environment variable before deployment. Do not commit passwords, API keys, environment files, or database backups.
