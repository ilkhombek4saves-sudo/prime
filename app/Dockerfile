FROM node:20-bookworm-slim
WORKDIR /app
COPY app/package.json app/package-lock.json* ./
RUN npm install
COPY app /app
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
