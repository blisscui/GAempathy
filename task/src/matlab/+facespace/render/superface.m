function renderResult = superface(selectionArchive, modelCtx, screenCtx, options)
%FACESPACE.RENDER.SUPERFACE Render "super face" lineup.
%   RENDERRESULT = FACESPACE.RENDER.SUPERFACE(SELECTIONARCHIVE, MODELCTX,
%   SCREENCtx, OPTIONS) composes the final generation of stimuli using the
%   previously selected faces stored within SELECTIONARCHIVE.
%
%   Expected SELECTIONARCHIVE fields:
%       - shapeVals : shape coefficients (shapeDim x k)
%       - texVals   : texture coefficients (textureDim x k)
%       - indices   : original indices corresponding to selected faces
%
%   OPTIONS may include:
%       - order         : explicit grid placement order (default Basel grid)
%       - gridSize      : [rows cols] for layout (default [3 4])
%       - logFn         : status logger

arguments
    selectionArchive struct
    modelCtx struct
    screenCtx struct
    options struct = struct()
end

logFn = getOption(options, 'logFn', []);
order = getOption(options, 'order', [5, 8, 2, 11, 4, 7, 6, 9, 1, 10, 3, 12]);

if ~isfield(selectionArchive, 'shapeVals') || isempty(selectionArchive.shapeVals)
    if ~isempty(logFn)
        logFn('Superface rendering skipped (no selections).');
    end
    renderResult = struct(
        'order', [], ...
        'destRects', [], ...
        'gridCenters', [], ...
        'srcRect', screenCtx.geometry.srcRect, ...
        'nextRect', screenCtx.geometry.nextRect, ...
        'images', {{}}, ...
        'nFaces', 0
    );
    return
end

numSelections = size(selectionArchive.shapeVals, 2);
order = order(1:numSelections);

population = struct(
    'shape', selectionArchive.shapeVals,
    'texture', selectionArchive.texVals
);

renderResult = facespace.render.grid(population, modelCtx, screenCtx, struct(
    'order', order,
    'logFn', logFn
));

renderResult.selectionIndices = selectionArchive.indices;
renderResult.population = population;

end

function value = getOption(options, field, defaultValue)
if isfield(options, field) && ~isempty(options.(field))
    value = options.(field);
else
    value = defaultValue;
end
end
