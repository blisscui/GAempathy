function params = inputs(config, logFn)
%FACESPACE.SETUP.INPUTS Gather experiment parameters.
%   PARAMS = FACESPACE.SETUP.INPUTS(CONFIG, LOGFN) returns a struct of
%   experiment parameters derived from configuration defaults and, when
%   permitted, an interactive dialog. LOGFN is an optional callback used
%   for status updates.

if nargin < 1 || isempty(config)
    config = struct();
end
if nargin < 2
    logFn = [];
end

if isfield(config, 'inputs')
    inputsCfg = config.inputs;
else
    inputsCfg = struct();
end

if ~isfield(inputsCfg, 'defaults')
    inputsCfg.defaults = struct();
end

defaults = normalizeDefaults(inputsCfg.defaults);
interactive = true;
if isfield(inputsCfg, 'interactive')
    interactive = logical(inputsCfg.interactive);
end

answer = [];

if interactive && exist('inputdlg', 'file') == 2
    prompt = {'Subject ID', '# Generations', 'Face Size (deg)', '# rows', '# columns', ...
        'Screen Width (cm)', 'Viewing Distance (cm)', 'Evolve Structure Texture'};
    dlg_title = 'Face Genetic Algorithm';
    num_lines = 1;
    def = {
        char(defaults.subjectId), ...
        num2str(defaults.generations), ...
        num2str(defaults.faceSize), ...
        num2str(defaults.rows), ...
        num2str(defaults.cols), ...
        num2str(defaults.screenWidthCm), ...
        num2str(defaults.viewDistanceCm), ...
        strtrim(sprintf('%d %d', defaults.structureOrTexture))
    };
    try
        answer = inputdlg(prompt, dlg_title, num_lines, def);
    catch err
        logMessage(sprintf('Input dialog failed (%s). Falling back to defaults.', err.message));
    end
    if isempty(answer)
        error('facespace:inputs:Cancelled', 'User cancelled input dialog.');
    end
else
    logMessage('Interactive input disabled or unavailable. Using defaults.');
    answer = {
        char(defaults.subjectId), ...
        num2str(defaults.generations), ...
        num2str(defaults.faceSize), ...
        num2str(defaults.rows), ...
        num2str(defaults.cols), ...
        num2str(defaults.screenWidthCm), ...
        num2str(defaults.viewDistanceCm), ...
        strtrim(sprintf('%d %d', defaults.structureOrTexture))
    };
end

params = struct();
params.subjectId = strtrim(answer{1});
params.nGenerations = parseScalar(answer{2}, defaults.generations, 'generations');
params.faceSizeDeg = parseScalar(answer{3}, defaults.faceSize, 'face size');
params.nRows = parseScalar(answer{4}, defaults.rows, 'rows');
params.nCols = parseScalar(answer{5}, defaults.cols, 'columns');
params.screenWidthCm = parseScalar(answer{6}, defaults.screenWidthCm, 'screen width');
params.viewDistanceCm = parseScalar(answer{7}, defaults.viewDistanceCm, 'view distance');
params.structureOrTexture = parseVector(answer{8}, defaults.structureOrTexture, 'structureOrTexture');
params.nFaces = params.nRows * params.nCols;
params.interactive = interactive;
params.defaults = defaults;

    function logMessage(message)
        if isempty(message)
            return
        end
        if ~isempty(logFn) && isa(logFn, 'function_handle')
            logFn(message);
        end
    end

end

function defaults = normalizeDefaults(defaults)
fields = struct(
    'subjectId', 'XX', ...
    'generations', 6, ...
    'faceSize', 6, ...
    'rows', 3, ...
    'cols', 4, ...
    'screenWidthCm', 60, ...
    'viewDistanceCm', 60, ...
    'structureOrTexture', [1 0]
);
keys = fieldnames(fields);
for i = 1:numel(keys)
    key = keys{i};
    if ~isfield(defaults, key) || isempty(defaults.(key))
        defaults.(key) = fields.(key);
    end
end
if isstring(defaults.subjectId)
    defaults.subjectId = char(defaults.subjectId);
end
end

function value = parseScalar(inputStr, fallback, label)
value = fallback;
if isempty(inputStr)
    return
end
if isstring(inputStr)
    inputStr = char(inputStr);
end
num = str2double(strtrim(inputStr));
if ~isnan(num)
    value = num;
else
    warning('facespace:inputs:ParseScalar', ...
        'Unable to parse %s from "%s". Using fallback %g.', label, inputStr, fallback);
end
end

function vec = parseVector(inputStr, fallback, label)
vec = fallback;
if isempty(inputStr)
    return
end
if isstring(inputStr)
    inputStr = char(inputStr);
end
vals = str2num(inputStr); %#ok<ST2NM>
if isempty(vals)
    warning('facespace:inputs:ParseVector', ...
        'Unable to parse %s from "%s". Using fallback.', label, inputStr);
else
    vec = vals;
end
end

