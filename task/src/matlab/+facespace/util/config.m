function cfg = config(source, overrides)
%FACESPACE.UTIL.CONFIG Load and validate experiment configuration.
%   CFG = FACESPACE.UTIL.CONFIG() loads the default configuration file
%   located at `<repo>/config/default.json`, applying built-in defaults and
%   validation rules.
%
%   CFG = FACESPACE.UTIL.CONFIG(PATH) loads configuration data from the
%   JSON file at PATH.
%
%   CFG = FACESPACE.UTIL.CONFIG(STRUCT) validates and augments the given
%   structure.
%
%   CFG = FACESPACE.UTIL.CONFIG(___, OVERRIDES) merges the supplied
%   overrides (struct) after loading the base configuration.

if nargin < 1 || isempty(source)
    source = defaultConfigPath();
end

if nargin < 2
    overrides = struct();
elseif ~isstruct(overrides)
    error('facespace:config:InvalidOverrides', ...
        'Overrides must be provided as a struct.');
end

if isstruct(source)
    cfg = source;
else
    if ~(ischar(source) || isstring(source))
        error('facespace:config:InvalidInput', ...
            'Expected a struct or file path, received %s.', class(source));
    end
    sourcePath = char(source);
    if exist(sourcePath, 'file') ~= 2
        error('facespace:config:NotFound', 'Config file not found: %s', sourcePath);
    end
    try
        cfg = jsondecode(fileread(sourcePath));
    catch err
        error('facespace:config:ParseError', ...
            'Failed to parse config file %s: %s', sourcePath, err.message);
    end
end

if ~isempty(overrides)
    cfg = mergeStructs(cfg, overrides);
end

cfg = applyDefaults(cfg);
validateConfig(cfg);

end

function path = defaultConfigPath()
thisFile = mfilename('fullpath');
utilDir = fileparts(thisFile);
facespaceDir = fileparts(utilDir);
matlabDir = fileparts(facespaceDir);
srcDir = fileparts(matlabDir);
repoRoot = fileparts(srcDir);
path = fullfile(repoRoot, 'config', 'default.json');
end

function merged = mergeStructs(base, overrides)
merged = base;
fields = fieldnames(overrides);
for i = 1:numel(fields)
    key = fields{i};
    overrideValue = overrides.(key);
    if isfield(merged, key)
        baseValue = merged.(key);
        if isstruct(baseValue) && isstruct(overrideValue)
            merged.(key) = mergeStructs(baseValue, overrideValue);
        else
            merged.(key) = overrideValue;
        end
    else
        merged.(key) = overrideValue;
    end
end
end

function cfg = applyDefaults(cfg)
if ~isfield(cfg, 'logging') || ~isstruct(cfg.logging)
    cfg.logging = struct();
end
if ~isfield(cfg.logging, 'dir') || isempty(cfg.logging.dir)
    cfg.logging.dir = 'logs';
end
if ~isfield(cfg.logging, 'level') || isempty(cfg.logging.level)
    cfg.logging.level = 'info';
end

if ~isfield(cfg, 'paths') || ~isstruct(cfg.paths)
    cfg.paths = struct();
end
if ~isfield(cfg.paths, 'baselModelDir') || isempty(cfg.paths.baselModelDir)
    cfg.paths.baselModelDir = fullfile('data', 'raw', 'BaselFaceModel', 'PublicMM1', 'matlab');
end

if ~isfield(cfg, 'screen') || ~isstruct(cfg.screen)
    cfg.screen = struct();
end
if ~isfield(cfg.screen, 'meanLUT') || isempty(cfg.screen.meanLUT)
    cfg.screen.meanLUT = 127;
end
if ~isfield(cfg.screen, 'skipSyncTests')
    cfg.screen.skipSyncTests = true;
end
if ~isfield(cfg.screen, 'openWindow')
    cfg.screen.openWindow = false;
end
if ~isfield(cfg.screen, 'mockRect') || numel(cfg.screen.mockRect) ~= 4
    cfg.screen.mockRect = [0 0 1920 1080];
end

if ~isfield(cfg, 'experiment') || ~isstruct(cfg.experiment)
    cfg.experiment = struct();
end
if ~isfield(cfg.experiment, 'emotions') || isempty(cfg.experiment.emotions)
    cfg.experiment.emotions = 13;
end
if ~isfield(cfg.experiment, 'generations') || isempty(cfg.experiment.generations)
    cfg.experiment.generations = 7;
end
if ~isfield(cfg.experiment, 'structureOrTexture') || isempty(cfg.experiment.structureOrTexture)
    cfg.experiment.structureOrTexture = [1 0];
end
if ~isfield(cfg.experiment, 'emotionLabels') || isempty(cfg.experiment.emotionLabels)
    cfg.experiment.emotionLabels = {
        'Amusement', 'Anger', 'Awe', 'Contempt', 'Disgust', ...
        'Embarrassment', 'Fear', 'Happiness', 'Interest', 'Pride', ...
        'Sadness', 'Shame', 'Surprise'
    };
end

if ~isfield(cfg, 'inputs') || ~isstruct(cfg.inputs)
    cfg.inputs = struct();
end
if ~isfield(cfg.inputs, 'interactive')
    cfg.inputs.interactive = true;
end
if ~isfield(cfg.inputs, 'defaults') || ~isstruct(cfg.inputs.defaults)
    cfg.inputs.defaults = struct();
end
cfg.inputs.defaults = applyInputDefaults(cfg.inputs.defaults);

end

function validateConfig(cfg)
requiredTop = {'logging', 'paths', 'screen', 'experiment', 'inputs'};
for i = 1:numel(requiredTop)
    key = requiredTop{i};
    if ~isfield(cfg, key)
        error('facespace:config:MissingField', 'Configuration missing required field: %s', key);
    end
end

if ~isfield(cfg.logging, 'dir')
    error('facespace:config:MissingField', 'Configuration missing logging.dir');
end

if ~isfield(cfg.paths, 'baselModelDir')
    error('facespace:config:MissingField', 'Configuration missing paths.baselModelDir');
end

if ~isfield(cfg.screen, 'meanLUT')
    error('facespace:config:MissingField', 'Configuration missing screen.meanLUT');
end
if ~isfield(cfg.screen, 'mockRect')
    error('facespace:config:MissingField', 'Configuration missing screen.mockRect');
end

if ~isfield(cfg.experiment, 'generations')
    error('facespace:config:MissingField', 'Configuration missing experiment.generations');
end
if ~isfield(cfg.experiment, 'emotionLabels')
    error('facespace:config:MissingField', 'Configuration missing experiment.emotionLabels');
end

requiredInputFields = {'subjectId', 'generations', 'faceSize', 'rows', 'cols', 'screenWidthCm', 'viewDistanceCm', 'structureOrTexture'};
for i = 1:numel(requiredInputFields)
    key = requiredInputFields{i};
    if ~isfield(cfg.inputs.defaults, key)
        error('facespace:config:MissingField', 'Configuration missing inputs.defaults.%s', key);
    end
end

end

function defaults = applyInputDefaults(defaults)
fields = struct(
    'subjectId', "XX", ...
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

end
