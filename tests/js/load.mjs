// Loads the page's scripts into a sandbox, as the browser would load them
// with ordinary script tags, and returns what they define. The scripts only
// touch the DOM when called on, so no browser is needed for their arithmetic.

import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const SITE = new URL('../../site/js/', import.meta.url);

// A first argument that isn't a file name is a set of globals to provide,
// such as stand-ins for Leaflet and the window.
export function load(...files) {
  const globals = typeof files[0] === 'object' ? files.shift() : {};
  const context = vm.createContext({ console, ...globals });
  for (const f of files) {
    vm.runInContext(readFileSync(new URL(f, SITE), 'utf8'), context, { filename: f });
  }
  // Top-level const and function declarations are shared between scripts
  // but aren't properties of the global object, so read them by name.
  return (...names) => vm.runInContext(`({ ${names.join(', ')} })`, context);
}
