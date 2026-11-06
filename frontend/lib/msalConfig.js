const tenantId = process.env.NEXT_PUBLIC_ENTRA_TENANT_ID;

export const msalConfig = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID || "",
    authority: tenantId
      ? `https://login.microsoftonline.com/${tenantId}`
      : "",
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

export const apiScope = process.env.NEXT_PUBLIC_ENTRA_API_SCOPE || "";

let msalInstancePromise;

export function initializeMsal() {
  if (!msalConfig.auth.clientId || !tenantId) {
    return Promise.reject(
      new Error(
        "Falta configurar el identificador de aplicación o el tenant de Microsoft Entra ID.",
      ),
    );
  }
  if (!msalInstancePromise) {
    msalInstancePromise = import("@azure/msal-browser").then(
      async ({ PublicClientApplication }) => {
        const instance = new PublicClientApplication(msalConfig);
        await instance.initialize();
        return instance;
      },
    );
  }
  return msalInstancePromise;
}
