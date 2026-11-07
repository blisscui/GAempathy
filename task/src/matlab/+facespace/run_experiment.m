function results = run_experiment(configOverrides)
%FACESPACE.RUN_EXPERIMENT Execute Basel face GA experiment workflow.
%   RESULTS = FACESPACE.RUN_EXPERIMENT(CONFIGOVERRIDES) bootstraps
%   configuration, logging, Basel model resources, PsychToolbox screen
%   state, and iterates through the genetic algorithm generations for each
%   target emotion. CONFIGOVERRIDES may be a struct or file path merged with
%   `config/default.json`.

if nargin < 1
    configOverrides = struct();
end

cfg = facespace.util.config(configOverrides);
logOpts = struct('dir', cfg.logging.dir, 'level', cfg.logging.level);
if isfield(cfg.logging, 'file') && ~isempty(cfg.logging.file)
    logOpts.file = cfg.logging.file;
end

log = facespace.util.logger(logOpts);
log.info('------------------------------------------------');
log.info('facespace.run_experiment started');
log.info('Log file: %s', log.file);

results = struct('config', cfg, 'logFile', log.file, 'timestamp', datetime('now'));

params = struct();
modelCtx = struct();
screenCtx = struct();

try
    params = facespace.setup.inputs(cfg, @(msg) log.info('%s', msg));
    log.info('Subject %s | Input generations: %d | Grid: %dx%d', ...
        params.subjectId, params.nGenerations, params.nRows, params.nCols);

    modelCtx = facespace.setup.model(cfg, @(msg) log.info('%s', msg));
    screenCtx = facespace.setup.screen(cfg, params, @(msg) log.info('%s', msg));

    shapeDim = size(modelCtx.model.shapePC, 2);
    textureDim = size(modelCtx.model.texPC, 2);
    gaOptionsBase = struct(
        'nFaces', params.nFaces, ...
        'shapeDim', shapeDim, ...
        'textureDim', textureDim, ...
        'structureRange', 2, ...
        'textureRange', 2, ...
        'structureOrTexture', params.structureOrTexture
    );

    totalGenerations = cfg.experiment.generations;
    emotions = cfg.experiment.emotionLabels;
    emotionCount = numel(emotions);
    if emotionCount ~= cfg.experiment.emotions
        log.warn('Configured emotion count (%d) differs from labels (%d).', ...
            cfg.experiment.emotions, emotionCount);
    end

    orderSeed = round(sum(1000 * clock)); %#ok<CLOCK>
    orderStream = RandStream('mt19937ar', 'Seed', orderSeed);
    testOrder = randperm(orderStream, emotionCount);

    results.params = params;
    results.model = modelCtx;
    results.screen = screenCtx;
    results.ga = struct(
        'options', gaOptionsBase, ...
        'functions', struct( ...
            'initialize', @facespace.ga.initialize_population, ...
            'breed', @facespace.ga.breed_offspring, ...
            'select', @facespace.ga.select_survivors ...
        ), ...
        'structureOrTexture', params.structureOrTexture ...
    );
    results.experiment = struct(
        'emotionLabels', {emotions}, ...
        'testOrder', testOrder, ...
        'totalGenerations', totalGenerations, ...
        'orderSeed', orderSeed ...
    );

    trialsCell = cell(emotionCount, totalGenerations);
    experimentTimer = tic;

    for seqIdx = 1:emotionCount
        emotionIdx = testOrder(seqIdx);
        emotionName = emotions{emotionIdx};
        log.info('--- Emotion %d/%d: %s ---', seqIdx, emotionCount, emotionName);

        trialsForEmotion = cell(1, totalGenerations);
        population = facespace.ga.initialize_population(gaOptionsBase);
        population.structureOrTexture = params.structureOrTexture;

        for genIdx = 1:totalGenerations
            isFinalGeneration = (genIdx == totalGenerations);
            trial = struct();
            trial.timestamp = datetime('now');
            trial.emotionIndex = emotionIdx;
            trial.emotionName = emotionName;
            trial.sequenceIndex = seqIdx;
            trial.generation = genIdx;
            trial.status = "pending";

            if ~isFinalGeneration
                renderResult = facespace.render.grid(population, modelCtx, screenCtx, struct(
                    'logFn', @(msg) log.debug('%s', msg)
                ));

                responseOptions = struct(
                    'interactive', params.interactive, ...
                    'allowMultiple', true, ...
                    'validIndices', 1:renderResult.nFaces, ...
                    'logFn', @(msg) log.debug('%s', msg)
                );
                responses = facespace.ui.collect_responses(screenCtx, renderResult, responseOptions);
                survivors = facespace.ga.select_survivors(responses.mask, struct(
                    'nFaces', renderResult.nFaces, ...
                    'targetOrder', renderResult.order
                ));

                population.selectionMask = survivors.mask;
                trial.population = population;
                trial.render = renderResult;
                trial.responses = responses;
                trial.survivors = survivors;
                trial.status = "completed";

                if genIdx < totalGenerations
                    population = facespace.ga.breed_offspring(population, struct(
                        'structureOrTexture', params.structureOrTexture, ...
                        'nFaces', gaOptionsBase.nFaces, ...
                        'shapeDim', gaOptionsBase.shapeDim, ...
                        'textureDim', gaOptionsBase.textureDim
                    ));
                end
            else
                archive = build_superface_archive(trialsForEmotion);
                if archive.count == 0
                    log.warn('No selections from prior generations; skipping superface.');
                    trial.status = "skipped";
                    trial.population = struct();
                    trial.render = struct();
                    trial.responses = struct('mask', [], 'indices', [], 'clickedNext', false, 'mode', 'skipped', 'order', []);
                    trial.survivors = struct('mask', [], 'indices', [], 'count', 0, 'targetOrder', []);
                else
                    renderResult = facespace.render.superface(archive, modelCtx, screenCtx, struct(
                        'logFn', @(msg) log.debug('%s', msg)
                    ));
                    responseOptions = struct(
                        'interactive', params.interactive, ...
                        'allowMultiple', false, ...
                        'validIndices', 1:renderResult.nFaces, ...
                        'logFn', @(msg) log.debug('%s', msg)
                    );
                    responses = facespace.ui.collect_responses(screenCtx, renderResult, responseOptions);
                    survivors = facespace.ga.select_survivors(responses.mask, struct(
                        'nFaces', renderResult.nFaces, ...
                        'targetOrder', renderResult.order
                    ));

                    archivePopulation = renderResult.population;
                    archivePopulation.selectionMask = survivors.mask;
                    archivePopulation.generation = genIdx;
                    archivePopulation.structureRange = gaOptionsBase.structureRange;
                    archivePopulation.textureRange = gaOptionsBase.textureRange;
                    archivePopulation.stream = [];
                    archivePopulation.structureOrTexture = params.structureOrTexture;
                    trial.population = archivePopulation;
                    trial.render = renderResult;
                    trial.responses = responses;
                    trial.survivors = survivors;
                    trial.status = "completed";
                end
            end

            trialsForEmotion{genIdx} = trial;
            selectedCount = 0;
            if isfield(trial, 'survivors') && isfield(trial.survivors, 'count')
                selectedCount = trial.survivors.count;
            end
            log.info('Generation %d/%d status: %s (selected %d).', ...
                genIdx, totalGenerations, char(trial.status), selectedCount);
        end

        trialsCell(emotionIdx, :) = trialsForEmotion;
    end

    results.durationSeconds = toc(experimentTimer);
    results.trials = trialsCell;
    results.status = "complete";
    artifacts = facespace.util.save_results(results, struct(
        'subjectId', params.subjectId, ...
        'timestamp', results.timestamp
    ));
    results.artifacts = artifacts;
    log.info('Results saved to %s', artifacts.matFile);
    if artifacts.logFile ~= ""
        log.info('Log copied to %s', artifacts.logFile);
    end
    log.info('Experiment loop complete (%.2f seconds).', results.durationSeconds);
    log.close();
    results.loggerClosed = true;
catch err
    log.error('Experiment terminated with error: %s', err.message);
    for k = 1:numel(err.stack)
        frame = err.stack(k);
        log.error('Stack %d: %s (line %d)', k, frame.name, frame.line);
    end

    if isfield(screenCtx, 'teardown') && isa(screenCtx.teardown, 'function_handle')
        screenCtx.teardown();
    end
    if isfield(modelCtx, 'teardown') && isa(modelCtx.teardown, 'function_handle')
        modelCtx.teardown();
    end

    log.close();
    rethrow(err);
end

results.logger = log;

end

function archive = build_superface_archive(trialsForEmotion)
shapeVals = [];
texVals = [];
indices = [];
generationIds = [];
withinGeneration = [];

for idx = 1:numel(trialsForEmotion)
    trial = trialsForEmotion{idx};
    if isempty(trial) || ~isfield(trial, 'population') || ~isfield(trial, 'survivors')
        continue;
    end
    if isempty(trial.survivors) || ~isfield(trial.survivors, 'indices')
        continue;
    end
    selected = trial.survivors.indices;
    if isempty(selected)
        continue;
    end
    shapeVals = [shapeVals, trial.population.shape(:, selected)]; %#ok<AGROW>
    texVals = [texVals, trial.population.texture(:, selected)]; %#ok<AGROW>
    generationIds = [generationIds, repmat(idx, 1, numel(selected))]; %#ok<AGROW>
    withinGeneration = [withinGeneration, selected]; %#ok<AGROW>
end

archive = struct();
archive.shapeVals = shapeVals;
archive.texVals = texVals;
archive.indices = [generationIds; withinGeneration]';
archive.count = size(shapeVals, 2);

end
