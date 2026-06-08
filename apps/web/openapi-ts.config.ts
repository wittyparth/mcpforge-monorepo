/* eslint-disable @typescript-eslint/no-explicit-any */
import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "./openapi.json",
  output: "./src/client",

  plugins: [
    "legacy/axios",
    {
      name: "@hey-api/sdk",
      asClass: true,
      operationId: true,
      classNameBuilder: "{{name}}Service",
      /**
       * FastAPI auto-generates operationIds in the form:
       *   ``register_api_v1_auth_register_post``
       *
       * We strip everything after ``_api_v1`` and keep only the
       * first segment so method names are clean:
       *   ``register``
       */
      methodNameBuilder: (op: any) => {
        const name: string = op.name ?? "";
        const idx = name.search(/api.?v1/i);
        const short = idx > 0 ? name.slice(0, idx) : name;
        return short.charAt(0).toLowerCase() + short.slice(1);
      },
    },
  ],
})
