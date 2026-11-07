function log = logger(opts)
%FACESPACE.UTIL.LOGGER Build a timestamped console/file logger.
%   LOG = FACESPACE.UTIL.LOGGER(OPTS) returns a struct of logging
%   callbacks (`debug`, `info`, `warn`, `error`, `close`) that emit
%   timestamped messages to the console and, optionally, to a file.
%
%   Supported OPTS fields:
%       - dir   : directory for log file (default: `logs`)
%       - file  : explicit file path; overrides `dir`
%       - level : minimum severity to emit (`debug`, `info`, `warn`, `error`)
%
%   Example:
%       log = facespace.util.logger(struct('dir', 'logs'));
%       log.info('Experiment booting for subject %s', subjectId);
%       log.close();

arguments
    opts struct = struct()
end

assignedLevel = 'info';
if isfield(opts, 'level') && ~isempty(opts.level)
    assignedLevel = lower(char(opts.level));
end

levels = struct('debug', 1, 'info', 2, 'warn', 3, 'error', 4);
if ~isfield(levels, assignedLevel)
    error('facespace:logger:InvalidLevel', 'Unsupported log level: %s', assignedLevel);
end

if isfield(opts, 'file') && ~isempty(opts.file)
    logFile = char(opts.file);
    logDir = fileparts(logFile);
    if isempty(logDir)
        logDir = '.';
    end
else
    logDir = '.';
    if isfield(opts, 'dir') && ~isempty(opts.dir)
        logDir = char(opts.dir);
    end
    timestamp = datestr(now, 'mm-dd-yyyy_HH-MM-SS');
    logFile = fullfile(logDir, sprintf('%s_logs.log', timestamp));
end

if exist(logDir, 'dir') ~= 7
    mkdir(logDir);
end

[fileId, message] = fopen(logFile, 'a');
if fileId == -1
    warning('facespace:logger:FileOpenFailed', ...
        'Unable to open log file (%s). Falling back to console only. Error: %s', logFile, message);
    fileId = [];
end

currentLevel = assignedLevel;

log = struct();
log.file = logFile;
log.level = currentLevel;
log.debug = @(msg, varargin) writeLog('debug', msg, varargin{:});
log.info  = @(msg, varargin) writeLog('info',  msg, varargin{:});
log.warn  = @(msg, varargin) writeLog('warn',  msg, varargin{:});
log.error = @(msg, varargin) writeLog('error', msg, varargin{:});
log.close = @closeLogger;

    function writeLog(level, message, varargin)
        if ~isfield(levels, level)
            warning('facespace:logger:UnknownLevel', 'Unknown log level: %s', level);
            return
        end
        if levels.(level) < levels.(currentLevel)
            return
        end
        if nargin < 2 || isempty(message)
            message = '';
        end
        if isstring(message)
            message = char(message);
        end
        if ~ischar(message)
            message = evalc('disp(message)');
        end
        if ~isempty(varargin)
            try
                formatted = sprintf(message, varargin{:});
            catch err
                warning('facespace:logger:FormatError', ...
                    'Failed to format log message: %s', err.message);
                formatted = message;
            end
        else
            formatted = message;
        end
        timestamp = datestr(now, 'yyyy-mm-dd HH:MM:SS.FFF');
        line = sprintf('[%s] %-5s %s', timestamp, upper(level), formatted);
        fprintf('%s\n', line);
        if ~isempty(fileId)
            fprintf(fileId, '%s\n', line);
            fflush(fileId);
        end
    end

    function closeLogger()
        if ~isempty(fileId)
            fclose(fileId);
            fileId = [];
        end
    end

end
