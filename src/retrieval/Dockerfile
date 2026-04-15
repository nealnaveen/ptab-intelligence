FROM public.ecr.aws/lambda/python:3.12-arm64

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

COPY handler.py .

CMD ["handler.handler"]
