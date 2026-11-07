function survivors = select_survivors(responses, options)
%FACESPACE.GA.SELECT_SURVIVORS Convert responses into selection metadata.
%   SURVIVORS = FACESPACE.GA.SELECT_SURVIVORS(RESPONSES, OPTIONS) accepts a
%   vector (logical/numeric) or struct describing participant selections and
%   returns a standardized representation.
%
%   RESPONSES may be:
%       - logical/numeric vector with 1 indicating selected faces
%       - struct with field `stimChosen` mirroring legacy format
%
%   OPTIONS can supply:
%       - `targetOrder`: permutation applied to presented stimuli
%       - `nFaces`: expected number of faces (validated if provided)

arguments
    responses
    options struct = struct()
end

if isstruct(responses)
    if isfield(responses, 'stimChosen')
        mask = logical(responses.stimChosen);
    else
        error('facespace:ga:select_survivors:MissingField', ...
            'Response struct missing ''stimChosen'' field.');
    end
else
    mask = responses ~= 0;
end

mask = mask(:)';

nFaces = numel(mask);
if isfield(options, 'nFaces') && ~isempty(options.nFaces)
    if options.nFaces ~= nFaces
        error('facespace:ga:select_survivors:SizeMismatch', ...
            'Response length (%d) does not match expected nFaces (%d).', nFaces, options.nFaces);
    end
else
    options.nFaces = nFaces;
end

if isfield(options, 'targetOrder') && ~isempty(options.targetOrder)
    targetOrder = options.targetOrder(:)';
else
    targetOrder = 1:nFaces;
end

selectedIndices = find(mask);

survivors = struct(
    'mask', mask,
    'indices', selectedIndices,
    'count', numel(selectedIndices),
    'targetOrder', targetOrder
);

end
