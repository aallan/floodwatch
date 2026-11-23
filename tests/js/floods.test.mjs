import { test } from 'node:test';
import assert from 'node:assert/strict';
import { load } from './load.mjs';

const { FloodWarnings } = load('utils.js', 'floods.js')('FloodWarnings');
const { summaryText } = FloodWarnings._internals;

test('the banner counts warnings by severity, most severe first', () => {
  assert.equal(summaryText([{ severity: 3 }]), '1 flood alert in force in the Taw catchment');
  assert.equal(summaryText([{ severity: 3 }, { severity: 3 }, { severity: 3 }]), '3 flood alerts in force in the Taw catchment');
  assert.equal(summaryText([{ severity: 3 }, { severity: 2 }, { severity: 1 }, { severity: 2 }]),
    '1 severe flood warning, 2 flood warnings and 1 flood alert in force in the Taw catchment');
});
