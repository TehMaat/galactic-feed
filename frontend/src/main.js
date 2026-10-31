import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/400-italic.css";
import "@fontsource/newsreader/500.css";
import "@fontsource/newsreader/600.css";
import "@fontsource/unbounded/500.css";
import "@fontsource/unbounded/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "./styles/base.css";
import "./styles/app.css";
import "./styles/extra.css";

import { mount } from "svelte";
import App from "./App.svelte";
import { registerServiceWorker } from "./lib/pwa.js";

mount(App, { target: document.getElementById("root") });
registerServiceWorker();
