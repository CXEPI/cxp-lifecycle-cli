'use strict';

/**
 * Checks targetVal object has the opts.field
 * @param {string} targetVal The string to lint
 * @param {Options} opts String requirements given by the linter ruleset
 **/
export default function (targetVal, opts) {
    if (typeof targetVal !== 'object') {
        return;
    }
    
    if (!opts || !opts.field) {
        return [
        {
            message: 'field option is missing',
        },
        ];
    }
    
    if (targetVal[opts.field] && targetVal[opts.field] === opts.value) {
        return;
    }
    
    return [
        {
        message: `${ opts.field } is not equal to ${ opts.value }`,
        },
    ];
}