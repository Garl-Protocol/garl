FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Clerk's publishable key must be inlined into the CLIENT bundle at build time
# (it gates the nav's Sign in/up + ClerkProvider). Without this ARG it isn't
# present during `next build`, so the client thinks Clerk is unconfigured.
# CLERK_SECRET_KEY is intentionally NOT here — it's a runtime-only server secret.
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

RUN npm run build

EXPOSE 3000

CMD ["sh", "-c", "npx next start -p ${PORT:-3000}"]
