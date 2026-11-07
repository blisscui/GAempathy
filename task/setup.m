function setup()
%SETUP Bootstrap the GAfaceSpace MATLAB environment.
%   Adds source directories to the MATLAB path and prepares data/log folders.
%
%   Usage:
%       >> setup
%
%   This script is idempotent and can be run multiple times.

repoRoot = fileparts(mfilename('fullpath'));

srcDir = fullfile(repoRoot, 'src', 'matlab');
if exist(srcDir, 'dir')
    addpath(genpath(srcDir));
else
    warning('Source directory not found: %s', srcDir);
end

scriptsDir = fullfile(repoRoot, 'scripts');
if exist(scriptsDir, 'dir')
    addpath(scriptsDir);
end

logsDir = fullfile(repoRoot, 'logs');
if ~exist(logsDir, 'dir')
    mkdir(logsDir);
end

dataDirs = {fullfile(repoRoot, 'data', 'interim'), ...
            fullfile(repoRoot, 'data', 'processed')};
for k = 1:numel(dataDirs)
    if ~exist(dataDirs{k}, 'dir')
        mkdir(dataDirs{k});
    end
end

configDir = fullfile(repoRoot, 'config');
if exist(configDir, 'dir')
    addpath(configDir);
end

disp('GAfaceSpace environment configured.');
end
