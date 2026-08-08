import { defineNuxtConfig } from "nuxt/config";

export default defineNuxtConfig({
  compatibilityDate: "2026-07-25",
  devtools: { enabled: false },
  modules: ["@nuxt/ui", "@nuxtjs/color-mode", "@nuxt/eslint"],
  css: ["~/assets/css/main.css"],
  ssr: true,
  typescript: {
    strict: true,
    typeCheck: false,
  },
  app: {
    head: {
      htmlAttrs: {
        lang: "en",
      },
      title: "Moksha AI",
      meta: [
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "description",
          content:
            "A private spiritual chat workspace grounded in indexed scriptures.",
        },
      ],
    },
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "/api/v1",
    },
  },
  colorMode: {
    classSuffix: "",
  },
});
