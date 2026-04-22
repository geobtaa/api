(() => {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  const RELOAD_FLAG = "btaa-sw-controller-reloaded";

  window.addEventListener("load", () => {
    void (async () => {
      try {
        const hadController = !!navigator.serviceWorker.controller;

        navigator.serviceWorker.addEventListener(
          "controllerchange",
          () => {
            if (!hadController || sessionStorage.getItem(RELOAD_FLAG)) {
              return;
            }

            sessionStorage.setItem(RELOAD_FLAG, "1");
            window.location.reload();
          },
          { once: true },
        );

        await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
          updateViaCache: "none",
        });

        if (!hadController) {
          sessionStorage.removeItem(RELOAD_FLAG);
        }
      } catch (error) {
        console.warn("Service worker registration failed:", error);
      }
    })();
  });
})();
