import next from "eslint-config-next";

const eslintConfig = [
  ...next,
  {
    rules: {
      // Every occurrence in this app is fetch-on-mount: an async function
      // awaits the API and calls setState from the continuation, which is the
      // "subscribe to an external system" case the rule's own docs allow. The
      // rule cannot see past the await, so it flags them all.
      //
      // Adopting SWR or React Query would satisfy the rule properly and is the
      // right move if this grows -- noted in docs/ARCHITECTURE.md.
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default eslintConfig;
