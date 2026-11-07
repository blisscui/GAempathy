function population = initialize_population(options)
%FACESPACE.GA.INITIALIZE_POPULATION Generate baseline GA population.
%   POPULATION = FACESPACE.GA.INITIALIZE_POPULATION(OPTIONS) creates the
%   initial set of shape and texture coefficient vectors used within the
%   Basel face genetic algorithm experiment.
%
%   Required OPTIONS fields:
%       - nFaces          : number of faces in the grid (rows * cols)
%       - shapeDim        : dimensionality of shape coefficient vectors
%       - textureDim      : dimensionality of texture coefficient vectors
%
%   Optional OPTIONS fields:
%       - structureRange  : symmetric magnitude applied to shape sampling
%       - textureRange    : symmetric magnitude applied to texture sampling
%       - stream          : RandStream instance for reproducibility
%       - generation      : generation index (defaults to 1)
%
%   The returned struct contains random coefficient matrices and metadata.

arguments
    options struct
end

requiredFields = {'nFaces', 'shapeDim', 'textureDim'};
for k = 1:numel(requiredFields)
    fld = requiredFields{k};
    if ~isfield(options, fld)
        error('facespace:ga:initialize_population:MissingField', ...
            'Options missing required field "%s".', fld);
    end
end

nFaces = options.nFaces;
shapeDim = options.shapeDim;
textureDim = options.textureDim;

structureRange = getOption(options, 'structureRange', 2);
textureRange = getOption(options, 'textureRange', 2);
structureOrTexture = getOption(options, 'structureOrTexture', [1 1]);

stream = getOption(options, 'stream', []);
if isempty(stream)
    seed = round(sum(1000 * clock)); %#ok<CLOCK>
    stream = RandStream('mt19937ar', 'Seed', seed);
else
    seed = NaN;
end

generation = getOption(options, 'generation', 1);

shapeCoords = structureRange * (2 * rand(stream, shapeDim, nFaces) - 1);
texCoords = textureRange * (2 * rand(stream, textureDim, nFaces) - 1);

population = struct(
    'generation', generation, ...
    'shape', shapeCoords, ...
    'texture', texCoords, ...
    'structureRange', structureRange, ...
    'textureRange', textureRange, ...
    'structureOrTexture', structureOrTexture, ...
    'stream', stream, ...
    'seed', seed, ...
    'selectionMask', false(1, nFaces)
);

end

function value = getOption(options, field, defaultValue)
if isfield(options, field) && ~isempty(options.(field))
    value = options.(field);
else
    value = defaultValue;
end
end
