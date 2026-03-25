FROM python:3.10

WORKDIR /app

COPY . .

RUN pip install flask gunicorn psutil

EXPOSE 5000

CMD ["python", "-m", "gunicorn", "-b", "0.0.0.0:5000", "app:app"]
