function offspring = breed_offspring(previous, options)
%FACESPACE.GA.BREED_OFFSPRING Generate next-generation coefficients.
%   OFFSPRING = FACESPACE.GA.BREED_OFFSPRING(PREVIOUS, OPTIONS) produces a
%   new population of shape and texture coefficients using selection data
%   from PREVIOUS. PREVIOUS must include fields:
%       - shape          : [shapeDim x nFaces] coefficients
%       - texture        : [textureDim x nFaces] coefficients
%       - selectionMask  : logical vector (1 x nFaces) denoting selections
%       - stream         : RandStream used during previous generation
%       - generation     : scalar index of previous generation
%
%   OPTIONS mirrors initialize_population with optional overrides:
%       - structureRange / textureRange
%       - structureOrTexture : logical vector [structure texture] enabling
%       - nFaces, shapeDim, textureDim (default derived from PREVIOUS)
%
%   The returned OFFSPRING struct matches the schema from
%   FACESPACE.GA.INITIALIZE_POPULATION with generation incremented.

arguments
    previous struct
    options struct = struct()
end

requiredPrev = {'shape', 'texture', 'selectionMask', 'stream', 'generation'};
for k = 1:numel(requiredPrev)
    fld = requiredPrev{k};
    if ~isfield(previous, fld)
        error('facespace:ga:breed_offspring:MissingField', ...
            'Previous generation missing required field "%s".', fld);
    end
end

nFaces = getOption(options, 'nFaces', size(previous.shape, 2));
shapeDim = getOption(options, 'shapeDim', size(previous.shape, 1));
textureDim = getOption(options, 'textureDim', size(previous.texture, 1));
structureRange = getOption(options, 'structureRange', previous.structureRange);
textureRange = getOption(options, 'textureRange', previous.textureRange);
structureOrTexture = getOption(options, 'structureOrTexture', [1 1]);

opts = struct(
    'nFaces', nFaces, ...
    'shapeDim', shapeDim, ...
    'textureDim', textureDim, ...
    'structureRange', structureRange, ...
    'textureRange', textureRange, ...
    'stream', previous.stream, ...
    'generation', previous.generation + 1
);

offspring = facespace.ga.initialize_population(opts);

offspring.parents.indices = find(previous.selectionMask);
offspring.parents.count = numel(offspring.parents.indices);
if offspring.parents.count == 0
    % No selections; keep random baseline.
    return
end

stream = offspring.stream;

successfulIdx = offspring.parents.indices;

halfFaces = max(1, floor(nFaces / 2));

if offspring.parents.count > 1
    for faceNum = 1:halfFaces
        if structureOrTexture(1)
            parentOrder = randperm(stream, offspring.parents.count);
            p1 = previous.shape(:, successfulIdx(parentOrder(1)));
            p2 = previous.shape(:, successfulIdx(parentOrder(2)));
            mask = rand(stream, shapeDim, 1) < 0.5;
            genes = p1;
            genes(mask) = p2(mask);
            offspring.shape(:, faceNum) = genes;
        end

        if structureOrTexture(2)
            parentOrder = randperm(stream, offspring.parents.count);
            p1 = previous.texture(:, successfulIdx(parentOrder(1)));
            p2 = previous.texture(:, successfulIdx(parentOrder(2)));
            mask = rand(stream, textureDim, 1) < 0.5;
            genes = p1;
            genes(mask) = p2(mask);
            offspring.texture(:, faceNum) = genes;
        end
    end
elseif offspring.parents.count == 1
    idx = successfulIdx(1);
    for faceNum = 1:halfFaces
        if structureOrTexture(1)
            baseGenes = previous.shape(:, idx);
            randomGenes = offspring.shape(:, faceNum);
            mask = rand(stream, shapeDim, 1) < 0.5;
            randomGenes(mask) = baseGenes(mask);
            offspring.shape(:, faceNum) = randomGenes;
        end
        if structureOrTexture(2)
            baseGenes = previous.texture(:, idx);
            randomGenes = offspring.texture(:, faceNum);
            mask = rand(stream, textureDim, 1) < 0.5;
            randomGenes(mask) = baseGenes(mask);
            offspring.texture(:, faceNum) = randomGenes;
        end
    end
end

offspring.selectionMask = false(1, nFaces);

offspring.stream = stream;
offspring.structureOrTexture = structureOrTexture;

offspring.parents.structureOrTexture = structureOrTexture;

end

function value = getOption(options, field, defaultValue)
if isfield(options, field) && ~isempty(options.(field))
    value = options.(field);
else
    value = defaultValue;
end
end
