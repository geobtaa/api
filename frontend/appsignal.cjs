const { Appsignal } = require("@appsignal/nodejs");
const { RemixInstrumentation } = require("opentelemetry-instrumentation-remix");

new Appsignal({
  active: true,
  name: "BTAA Geospatial API - Dev - Frontend",
  additionalInstrumentations: [new RemixInstrumentation()],
});
