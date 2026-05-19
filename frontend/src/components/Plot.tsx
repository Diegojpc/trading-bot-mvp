/* ═══════════════════════════════════════════════════════════════════════
   Shared Plotly component — uses factory pattern with plotly.js-dist-min.
   ═══════════════════════════════════════════════════════════════════════ */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
import factoryModule from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';

// CJS interop: the module exports { default: fn }
const createPlotlyComponent = typeof factoryModule === 'function'
  ? factoryModule
  : (factoryModule as any).default;

const Plot = createPlotlyComponent(Plotly);
export default Plot;
