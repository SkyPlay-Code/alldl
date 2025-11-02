# Dockerfile

# Start with an official Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install ffmpeg and other build tools
# apt-get update && apt-get install -y: Updates the package list and installs ffmpeg.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg

# Copy the file that lists our Python dependencies
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all of your application code into the container
COPY . .

# Tell the world that port 10000 is open (Render's required port for web services)
EXPOSE 10000

# The command to run your application
# Gunicorn is told to listen on all interfaces (0.0.0.0) on port 10000.
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]