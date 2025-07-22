'use strict';

/**
 * Checks targetVal object has the opts.field
 * @param {string} targetVal The string to lint
 * @param {Options} opts String requirements given by the linter ruleset
 */
export default function (targetVal, opts) {
  if (typeof targetVal !== 'object') {
    return;
  }

  // Check if opts is defined and has the fields property
  if (!opts || !opts.fields) {
    return [
      {
        message: 'missing fields option',
      },
    ];
  }
  if (!Array.isArray(opts.fields)) {
    return [
      {
        message: 'fields option is not an array',
      },
    ];
  }
  if (opts.fields.length === 0) {
    return [
      {
        message: 'fields option is empty',
      },
    ];
  }

  // Check if all fields are present in the targetVal object
  const missingFields = opts.fields.filter(field => !targetVal[field]);
  if (missingFields.length > 0) {
    return [
      {
        message: `Missing fields: ${missingFields.join(', ')}`,
      },
    ];
  }

  // If targetVal is a json object, check if all fields are present
  if (typeof targetVal === 'object' && !Array.isArray(targetVal)) {
    for (const field of opts.fields) {
      if (!(field in targetVal)) {
        return [
          {
            message: `Missing field: ${field}`,
          },
        ];
      }
    }
  }

  // If we got here, all fields are present
  return;
}
