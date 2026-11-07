function modelCtx = model(config, logFn)
%FACESPACE.SETUP.MODEL Load Basel Face Model resources.
%   MODELCtx = FACESPACE.SETUP.MODEL(CONFIG, LOGFN) ensures the Basel face
%   model directory is on the MATLAB path, invokes `load_model` and `defrp`
%   from the Basel distribution, and returns a struct containing the model
%   data and render parameters.

if nargin < 1 || isempty(config)
    config = struct();
end
if nargin < 2
    logFn = [];
end

if ~isfield(config, 'paths') || ~isfield(config.paths, 'baselModelDir')
    error('facespace:model:MissingPath', ...
        'Configuration must supply paths.baselModelDir.');
end

modelDir = config.paths.baselModelDir;
if isstring(modelDir)
    modelDir = char(modelDir);
end

if exist(modelDir, 'dir') ~= 7
    error('facespace:model:DirNotFound', ...
        'Basel model directory does not exist: %s', modelDir);
end

logMessage(sprintf('Loading Basel Face Model from %s', modelDir));
pathAdded = addpath(modelDir);
addedPaths = strsplit(pathAdded, pathsep);
addedPaths = addedPaths(~cellfun('isempty', addedPaths));

try
    [modelData, msz] = load_model();
    renderParams = defrp();
    renderParams.phi = 0;

    modelCtx = struct(
        'status', "loaded", ...
        'model', modelData, ...
        'size', msz, ...
        'renderParams', renderParams, ...
        'modelDir', modelDir, ...
        'pathsAdded', {addedPaths}, ...
        'teardown', @() teardownPath(addedPaths)
    );

    logMessage('Basel Face Model loaded successfully.');
catch err
    logMessage(sprintf('Failed to load Basel Face Model: %s', err.message));
    teardownPath(addedPaths);
    rethrow(err);
end

    function logMessage(message)
        if ~isempty(logFn) && isa(logFn, 'function_handle')
            logFn(message);
        end
    end

    function teardownPath(pathsToRemove)
        if isempty(pathsToRemove)
            return
        end
        for idx = 1:numel(pathsToRemove)
            candidate = pathsToRemove{idx};
            if ~isempty(candidate) && exist(candidate, 'dir')
                rmpath(candidate);
            end
        end
    end

end
