export default {
  extends: ["stylelint-config-standard"],
  overrides: [
    {
      files: ["**/*.vue"],
      customSyntax: "postcss-html",
    },
  ],
  rules: {
    "custom-property-empty-line-before": null,
    "import-notation": null,
    "media-feature-range-notation": "prefix",
    "no-descending-specificity": null,
    "selector-class-pattern": null,
    "selector-id-pattern": null,
    "selector-pseudo-class-no-unknown": [
      true,
      {
        ignorePseudoClasses: ["deep", "global"],
      },
    ],
  },
};
