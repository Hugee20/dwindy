import {tests as apiTests} from './api-client.test.js';
import {tests as componentTests} from './dwindy-chat.test.js';
const results = [];
for (const [name, run] of [...apiTests, ...componentTests]) {
  try { await run(); results.push({name, pass: true}); }
  catch (error) { results.push({name, pass: false, error: String(error.stack || error)}); }
}
globalThis.testResults = results;
document.querySelector('#results').textContent = JSON.stringify(results, null, 2);
document.title = results.every(r => r.pass) ? `PASS ${results.length}` : 'FAIL';
