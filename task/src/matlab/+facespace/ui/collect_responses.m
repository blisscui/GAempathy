function responses = collect_responses(screenCtx, layout, options)
%FACESPACE.UI.COLLECT_RESPONSES Collect participant selections from grid.
%   RESPONSES = FACESPACE.UI.COLLECT_RESPONSES(SCREENCtx, LAYOUT, OPTIONS)
%   handles interactive mouse/keyboard input (when PsychToolbox is
%   available) as well as simulated selections for headless execution.
%
%   Required layout fields:
%       - destRects      : [n x 4] destination rectangles for stimuli
%       - gridCenters    : [n x 2] center coordinates of each cell
%       - nextRect       : 1x4 rectangle for the NEXT button
%       - nFaces         : number of stimuli displayed
%
%   OPTIONS fields:
%       - interactive    : logical flag allowing interactive input
%       - allowMultiple  : logical flag (true for generations 1-6)
%       - validIndices   : indices permitted to toggle (for super faces)
%       - logFn          : logging callback (optional)
%       - simulatedMask  : allow pre-defined mask for automated runs
%
%   Returns struct with fields:
%       - mask           : logical selection mask (1 x nFaces)
%       - indices        : selected indices
%       - clickedNext    : boolean indicating completion
%       - mode           : 'interactive' | 'simulated'
%       - history        : struct with timestamps/clicks (lightweight)

arguments
    screenCtx struct
    layout struct
    options struct = struct()
end

nFaces = layout.nFaces;
order = getField(layout, 'order', 1:nFaces);
logFn = getOption(options, 'logFn', []);
allowMultiple = getOption(options, 'allowMultiple', true);
interactive = getOption(options, 'interactive', true) && ...
    isfield(screenCtx, 'status') && screenCtx.status == "open";
validIndices = getOption(options, 'validIndices', 1:nFaces);
simulatedMask = getOption(options, 'simulatedMask', []);

% Headless or simulated path
if ~interactive
    if isempty(simulatedMask)
        mask = false(1, nFaces);
    else
        mask = logical(simulatedMask(:)');
    end
    responses = formatResponse(mask, true, 'simulated', struct(), order);
    logMessage(logFn, sprintf('Collect responses headless (n=%d).', nnz(mask)));
    return
end

windowPtr = screenCtx.windowPtr;
nextRect = layout.nextRect;
destRectsUsed = layout.destRects(order, :);
centers = layout.gridCenters(order, :);

mask = false(1, nFaces);
validMask = false(1, nFaces);
validMask(validIndices) = true;

% Prepare keyboards
[deviceIdx, deviceNames] = GetKeyboardIndices;
keyboardIdx = [];
if ~isempty(deviceIdx)
    keyboardIdx = deviceIdx(1);
    targetName = 'Magic Keyboard';
    hits = strcmpi(deviceNames, targetName);
    if any(hits)
        keyboardIdx = deviceIdx(find(hits, 1, 'first'));
    end
end

if ~isempty(keyboardIdx)
    KbQueueCreate(keyboardIdx);
    KbQueueStart(keyboardIdx);
end

ShowCursor;
clickedNext = false;
clickHistory = [];
lastKey = '';

try
    while ~clickedNext
        [mx, my, buttons] = GetMouse(windowPtr);

        if any(buttons)
            while any(buttons)
                [mx, my, buttons] = GetMouse(windowPtr);
            end
        end

        WaitSecs(0.01);

        % Poll keyboard for escape sequence
        if ~isempty(keyboardIdx)
            [pressed, firstPress] = KbQueueCheck(keyboardIdx);
            if pressed
                keyNames = KbName(firstPress);
                if iscell(keyNames)
                    keyNames = keyNames{1};
                end
                if strcmp(lastKey, 'space') && strcmpi(keyNames, 'ESCAPE')
                    Screen('CloseAll');
                    error('facespace:ui:Abort', 'Escape sequence detected.');
                end
                lastKey = keyNames;
            end
        end

        [mx, my, buttons] = GetMouse(windowPtr);
        if ~any(buttons)
            continue
        end

        clickHistory(end + 1).timestamp = GetSecs; %#ok<AGROW>
        clickHistory(end).position = [mx, my];

        if mx > nextRect(1) && mx < nextRect(3) && my > nextRect(2) && my < nextRect(4)
            if allowMultiple || any(mask)
                clickedNext = true;
                logMessage(logFn, 'Next button clicked.');
            else
                logMessage(logFn, 'Next requires at least one selection.');
                continue;
            end
        else
            % Determine nearest stimulus center
            distances = hypot(mx - centers(:, 1)', my - centers(:, 2)');
            validIdxList = find(validMask);
            if isempty(validIdxList)
                continue;
            end
            [~, relIdx] = min(distances(validMask));
            selectedIdx = validIdxList(relIdx);

            if allowMultiple
                mask(selectedIdx) = ~mask(selectedIdx);
            else
                mask(:) = false;
                mask(selectedIdx) = true;
            end

            highlightSelection(windowPtr, destRectsUsed, mask, validMask);
        end

        Screen('Flip', windowPtr, [], 1);
    end
catch err
    if ~isempty(keyboardIdx)
        KbQueueRelease(keyboardIdx);
    end
    rethrow(err);
end

if ~isempty(keyboardIdx)
    KbQueueRelease(keyboardIdx);
end

responses = formatResponse(mask, true, 'interactive', struct('clicks', clickHistory), order);
logMessage(logFn, sprintf('Selections recorded (%d chosen).', nnz(mask)));

end

function highlightSelection(windowPtr, destRects, mask, validMask)
for idx = find(validMask)
    color = [128 128 128];
    if mask(idx)
        color = [0 255 0];
    end
    Screen('FrameRect', windowPtr, color, destRects(idx, :), 2);
end
end

function responses = formatResponse(mask, clickedNext, mode, history, order)
responses = struct(
    'mask', logical(mask), ...
    'indices', find(mask), ...
    'clickedNext', clickedNext, ...
    'mode', mode, ...
    'history', history, ...
    'order', order
);
end

function value = getOption(options, field, defaultValue)
if isfield(options, field) && ~isempty(options.(field))
    value = options.(field);
else
    value = defaultValue;
end
end

function value = getField(s, field, defaultValue)
if isfield(s, field) && ~isempty(s.(field))
    value = s.(field);
else
    value = defaultValue;
end
end

function logMessage(logFn, message)
if ~isempty(logFn) && isa(logFn, 'function_handle')
    logFn(message);
end
end
