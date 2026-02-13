FROM node:20-bookworm-slim
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --include=optional \
    && ROLLUP_VERSION=$(node -p "require('./node_modules/rollup/package.json').version") \
    && ROLLUP_NATIVE_PKG=$(node -p "const libc = (process.report?.getReport()?.header?.glibcVersionRuntime ? 'gnu' : 'musl'); '@rollup/rollup-linux-' + process.arch + '-' + libc") \
    && npm install --no-save "${ROLLUP_NATIVE_PKG}@${ROLLUP_VERSION}"
COPY frontend /app
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
