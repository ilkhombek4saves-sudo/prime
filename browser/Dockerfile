FROM mcr.microsoft.com/playwright:v1.40.0-jammy

WORKDIR /app

COPY package.json ./
RUN npm install --production

# Install Chromium for Playwright
RUN npx playwright install chromium

COPY server.js ./

EXPOSE 3001

CMD ["node", "server.js"]
