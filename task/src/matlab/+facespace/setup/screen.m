function screenCtx = screen(config, params, logFn)
%FACESPACE.SETUP.SCREEN Configure PsychToolbox screen and geometry.
%   SCREENCtx = FACESPACE.SETUP.SCREEN(CONFIG, PARAMS, LOGFN) opens the
%   PsychToolbox window when requested and returns geometry metadata for
%   rendering GA stimuli. PARAMS should include fields produced by
%   facespace.setup.inputs (rows, cols, faceSizeDeg, screenWidthCm,
%   viewDistanceCm).

if nargin < 1 || isempty(config)
    config = struct();
end
if nargin < 2
    params = struct();
end
if nargin < 3
    logFn = [];
end

if isfield(config, 'screen')
    screenCfg = config.screen;
else
    screenCfg = struct();
end

openWindow = isfield(screenCfg, 'openWindow') && screenCfg.openWindow;

windowPtr = [];
winRect = getField(screenCfg, 'mockRect', [0 0 1920 1080]);
frameRate = 0;
screenId = [];
status = "skipped";
teardownFn = @noopTeardown;

if openWindow && exist('Screen', 'file') == 3
    try
        if getField(screenCfg, 'skipSyncTests', false)
            Screen('Preference', 'SkipSyncTests', 1);
        end
        if isfield(screenCfg, 'screenId')
            screenId = screenCfg.screenId;
        else
            screenId = max(Screen('Screens'));
        end
        logMessage(sprintf('Opening screen ID %d', screenId));

        meanLUT = getField(screenCfg, 'meanLUT', 127);
        [windowPtr, winRect] = Screen('OpenWindow', screenId, meanLUT);
        frameRate = Screen('FrameRate', windowPtr);
        status = "open";
        teardownFn = @() tearDownWindow(windowPtr);
        logMessage(sprintf('Screen opened (%d x %d @ %.2f Hz).', ...
            winRect(3) - winRect(1), winRect(4) - winRect(2), frameRate));
    catch err
        logMessage(sprintf('Screen initialization failed: %s', err.message));
        if exist('windowPtr', 'var') && ~isempty(windowPtr)
            Screen('CloseAll');
        end
        rethrow(err);
    end
elseif openWindow
    logMessage('PsychToolbox Screen() not available; falling back to mock rect.');
    status = "unavailable";
else
    logMessage('Screen initialization skipped (openWindow=false).');
end

geometry = computeGeometry(winRect, params);

screenCtx = struct(
    'status', status, ...
    'windowPtr', windowPtr, ...
    'winRect', winRect, ...
    'frameRate', frameRate, ...
    'screenId', screenId, ...
    'geometry', geometry, ...
    'teardown', teardownFn
);

    function logMessage(message)
        if ~isempty(logFn) && isa(logFn, 'function_handle')
            logFn(message);
        end
    end

end

function rect = getField(s, name, defaultValue)
if isfield(s, name) && ~isempty(s.(name))
    rect = s.(name);
else
    rect = defaultValue;
end
end

function geom = computeGeometry(winRect, params)
if ~isfield(params, 'nRows'); params.nRows = 3; end
if ~isfield(params, 'nCols'); params.nCols = 4; end
if ~isfield(params, 'faceSizeDeg'); params.faceSizeDeg = 6; end
if ~isfield(params, 'screenWidthCm'); params.screenWidthCm = 60; end
if ~isfield(params, 'viewDistanceCm'); params.viewDistanceCm = 60; end

scrnWidthCm = params.screenWidthCm;
viewDistCm = params.viewDistanceCm;

scrnWidthPix = winRect(3) - winRect(1);
scrnHeightPix = winRect(4) - winRect(2);
screenCenter = [winRect(1) + scrnWidthPix / 2, winRect(2) + scrnHeightPix / 2];

if viewDistCm == 0
    pixPerDeg = NaN;
else
    scrnWidthDeg = 2 * atand((0.5 * scrnWidthCm) / viewDistCm);
    pixPerDeg = scrnWidthPix / scrnWidthDeg;
end

imSize = pixPerDeg * params.faceSizeDeg;
srcRect = [0 0 imSize imSize];

[xFactor, yFactor] = meshgrid((1:params.nCols) - params.nCols / 2 - 0.5, ...
    (1:params.nRows) - params.nRows / 2 - 0.5);

xStimCenter = screenCenter(1) + xFactor * imSize * 1.2;
yStimCenter = screenCenter(2) + yFactor * imSize * 1.2;

nFaces = params.nRows * params.nCols;
destRects = zeros(nFaces, 4);
gridCenters = zeros(nFaces, 2);

for idx = 1:nFaces
    row = ceil(idx / params.nCols);
    col = idx - (row - 1) * params.nCols;
    cx = xStimCenter(row, col);
    cy = yStimCenter(row, col);
    destRects(idx, :) = centerRectOnPoint(srcRect, cx, cy);
    gridCenters(idx, :) = [cx, cy];
end

nextSizeDeg = 4;
nextRect = centerRectOnPoint([0 0 nextSizeDeg * pixPerDeg nextSizeDeg * pixPerDeg], ...
    winRect(3) - nextSizeDeg * pixPerDeg, screenCenter(2));

geom = struct(
    'pixPerDeg', pixPerDeg, ...
    'imageSize', imSize, ...
    'srcRect', srcRect, ...
    'destRects', destRects, ...
    'gridCenters', gridCenters, ...
    'nextRect', nextRect, ...
    'screenCenter', screenCenter, ...
    'nRows', params.nRows, ...
    'nCols', params.nCols
);

end

function rect = centerRectOnPoint(baseRect, x, y)
width = baseRect(3) - baseRect(1);
height = baseRect(4) - baseRect(2);
rect = [x - width / 2, y - height / 2, x + width / 2, y + height / 2];
end

function noopTeardown()
end

function tearDownWindow(ptr)
if exist('Screen', 'file') == 3 && ~isempty(ptr)
    Screen('Close', ptr);
end
end
