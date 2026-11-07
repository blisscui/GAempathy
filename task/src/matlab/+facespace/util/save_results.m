function artifact = save_results(results, options)
%FACESPACE.UTIL.SAVE_RESULTS Persist experiment output to disk.
%   ARTIFACT = FACESPACE.UTIL.SAVE_RESULTS(RESULTS, OPTIONS) writes a
%   sanitized snapshot of the experiment RESULTS to the `data/interim`
%   directory, organized by subject and timestamp. OPTIONS may specify:
%       - subjectId (char) : override subject identifier
%       - timestamp (datetime) : override timestamp for folder naming
%       - baseDir (char)   : override root output directory
%
%   Returns ARTIFACT struct containing output directory and file paths.

arguments
    results struct
    options.subjectId {mustBeTextScalar} = ""
    options.timestamp datetime = NaT
    options.baseDir {mustBeTextScalar} = ""
end

subjectId = char(options.subjectId);
if isempty(subjectId)
    if isfield(results, 'params') && isfield(results.params, 'subjectId')
        subjectId = char(results.params.subjectId);
    else
        subjectId = 'unknown';
    end
end

runTimestamp = options.timestamp;
if isnat(runTimestamp)
    if isfield(results, 'timestamp')
        runTimestamp = results.timestamp;
    else
        runTimestamp = datetime('now');
    end
end

subjectSlug = lower(regexprep(subjectId, '[^a-z0-9]+', '_'));
if isempty(subjectSlug)
    subjectSlug = 'subject';
end

if isempty(options.baseDir)
    baseDir = fullfile(repo_root(), 'data', 'interim');
else
    baseDir = char(options.baseDir);
end

runFolder = datestr(runTimestamp, 'yyyy-mm-dd_HH-MM-SS');
outputDir = fullfile(baseDir, subjectSlug, runFolder);
if exist(outputDir, 'dir') ~= 7
    mkdir(outputDir);
end

persistable = struct();
persistable.subjectId = subjectId;
persistable.timestamp = runTimestamp;
if isfield(results, 'durationSeconds')
    persistable.durationSeconds = results.durationSeconds;
end
persistable.status = get_field(results, 'status', "unknown");
if isfield(results, 'params')
    persistable.params = results.params;
end
if isfield(results, 'experiment')
    persistable.experiment = results.experiment;
end
if isfield(results, 'ga')
    gaSummary = results.ga;
    if isfield(gaSummary, 'functions')
        gaSummary = rmfield(gaSummary, 'functions');
    end
    persistable.ga = gaSummary;
end
if isfield(results, 'config')
    persistable.config = results.config;
end
if isfield(results, 'trials')
    persistable.trials = sanitize_trials(results.trials);
end

experimentResults = persistable; %#ok<NASGU>
matFile = fullfile(outputDir, 'facespace_results.mat');
save(matFile, 'experimentResults', '-v7.3');

copiedLog = "";
if isfield(results, 'logFile') && exist(results.logFile, 'file') == 2
    [~, logName, logExt] = fileparts(results.logFile);
    destLog = fullfile(outputDir, [logName, logExt]);
    try
        copyfile(results.logFile, destLog);
        copiedLog = destLog;
    catch copyErr
        warning('facespace:save_results:LogCopyFailed', ...
            'Unable to copy log file: %s', copyErr.message);
    end
end

artifact = struct(
    'directory', outputDir, ...
    'matFile', matFile, ...
    'logFile', copiedLog, ...
    'subjectId', subjectId, ...
    'timestamp', runTimestamp
);

end

function root = repo_root()
thisFile = mfilename('fullpath');
utilDir = fileparts(thisFile);
facespaceDir = fileparts(utilDir);
matlabDir = fileparts(facespaceDir);
srcDir = fileparts(matlabDir);
root = fileparts(srcDir);
end

function trials = sanitize_trials(trials)
for row = 1:size(trials, 1)
    for col = 1:size(trials, 2)
        trial = trials{row, col};
        if isempty(trial) || ~isstruct(trial)
            continue;
        end
        if isfield(trial, 'population') && isstruct(trial.population)
            if isfield(trial.population, 'stream')
                trial.population.stream = [];
            end
        end
        trials{row, col} = trial;
    end
end
end

function value = get_field(s, field, defaultValue)
if isfield(s, field)
    value = s.(field);
else
    value = defaultValue;
end
end
