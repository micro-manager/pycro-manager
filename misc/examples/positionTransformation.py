from misc.positions import PositionList

"""This example demonstrates how to generate new imaging positions from a set of positions after the sample has been picked up and likely shifted or rotated.
This method relies on measuring a set of reference positions (at least 3) before and after moving the dish. You can then use these positions to generate an 
affine transform. This affine transform can then be applied to your original cell positions in order to generate a new set of positions for the same cells.
In the case of a standard cell culture dish it is best to use the corners of the glass coverslip as your reference locations.
"""
preTreatRefPositions = PositionList.load(
    r"experimentPath\preCorners.pos"
)  # Load the position list of the coverslip corners taken at the beginning of the experiment.
postTreatRefPositions = PositionList.load(
    r"experimentPath\postCorners.pos"
)  # Load the position list of the coverslip corners after placing the dish back on the microscope after treatment.
transformMatrix = preTreatRefPositions.getAffineTransform(
    postTreatRefPositions
)  # Generate an affine transform describing the difference between the two position lists.
preTreatCellPositions = PositionList.load(
    r"experimentPath\position_list1.pos"
)  # Load the positions of the cells we are measuring before the dish was removed.
postTreatCellPositions = preTreatCellPositions.applyAffineTransform(
    transformMatrix
)  # Transform the cell positions to the new expected locations.
postTreatCellPositions.save(
    r"experimentPath\transformedPositions.pos"
)  # Save the new positions to a file that can be loaded by Micro-Manager.

preTreatRefPositions.plot()
postTreatRefPositions.plot()
