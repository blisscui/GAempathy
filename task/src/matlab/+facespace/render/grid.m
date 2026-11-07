function renderResult = grid(population, modelCtx, screenCtx, options)
%FACESPACE.RENDER.GRID Draw GA population into grid layout.
%   RENDERRESULT = FACESPACE.RENDER.GRID(POPULATION, MODELCTX, SCREENCtx)
%   renders face stimuli using Basel model coefficients and the PsychToolbox
%   window described by SCREENCtx. OPTIONS may supply:
%       - order: permutation of grid cells
%       - logFn: function handle for status updates
%
%   The returned struct includes the display order, destination rectangles,
%   and captured images when no window is available.

arguments
    population struct
    modelCtx struct
    screenCtx struct
    options struct = struct()
end

logFn = getOption(options, 'logFn', []);
order = getOption(options, 'order', []);

requiredPopFields = {'shape', 'texture'};
for k = 1:numel(requiredPopFields)
    fld = requiredPopFields{k};
    if ~isfield(population, fld)
        error('facespace:render:grid:MissingField', ...
            'Population missing required field "%s".', fld);
    end
end

model = modelCtx.model;
rp = modelCtx.renderParams;
geom = screenCtx.geometry;

nFaces = size(population.shape, 2);

if isempty(order)
    if isfield(population, 'stream') && ~isempty(population.stream)
        order = randperm(population.stream, nFaces);
    else
        order = randperm(nFaces);
    end
end

if numel(order) ~= nFaces
    error('facespace:render:grid:OrderMismatch', ...
        'Order vector length (%d) must match number of faces (%d).', numel(order), nFaces);
end

windowPtr = screenCtx.windowPtr;
useScreen = ~isempty(windowPtr) && exist('Screen', 'file') == 3;

capturedImages = cell(1, nFaces);

for idx = 1:nFaces
    mesh = coef2object(population.shape(:, idx), model.shapeMU, model.shapePC, model.shapeEV);
    tex = coef2object(population.texture(:, idx), model.texMU, model.texPC, model.texEV);

    fig = figure(1); %#ok<LFIG>
    set(fig, 'Visible', 'off');
    rp.width = 400;
    rp.height = 400;
    display_face(mesh, tex, model.tl, rp);
    set(fig, 'Color', [0.5 0.5 0.5]);
    frame = getframe(fig);
    img = frame.cdata;
    capturedImages{idx} = img;
    clf(fig);

    if useScreen
        destIndex = order(idx);
        destRect = geom.destRects(destIndex, :);
        stimTex = Screen('MakeTexture', windowPtr, img);
        Screen('DrawTexture', windowPtr, stimTex, [], destRect);
        Screen('Close', stimTex);
    end
end

if useScreen
    Screen('Flip', windowPtr, [], 1);
end

renderResult = struct(
    'order', order,
    'destRects', geom.destRects,
    'gridCenters', geom.gridCenters,
    'srcRect', geom.srcRect,
    'nextRect', geom.nextRect,
    'images', {capturedImages}, ...
    'nFaces', nFaces
);

if ~isempty(logFn)
    logFn(sprintf('Rendered %d faces into grid.', nFaces));
end

end

function value = getOption(options, field, defaultValue)
if isfield(options, field) && ~isempty(options.(field))
    value = options.(field);
else
    value = defaultValue;
end
end
