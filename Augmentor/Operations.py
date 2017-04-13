from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *

from PIL import Image, ImageOps
from .ImageUtilities import extract_paths_and_extensions
import math
from math import floor, ceil

import numpy as np
from skimage import img_as_ubyte
from skimage import transform

import os
import random
import warnings

# Python 2-3 compatibility - not currently needed.
# try:
#    from StringIO import StringIO
# except ImportError:
#    from io import StringIO


class Operation(object):
    """
    The class :class:`Operation` represents the Base class for all operations
    that can be performed. Inherit from :class:`Operation`, overload its
    methods, and instantiate super to create a new operation.
    """
    def __init__(self, probability):
        self.probability = probability

    def __str__(self):
        return self.__class__.__name__

    def perform_operation(self, image):
        raise RuntimeError("Illegal call to base class.")

    @staticmethod
    def extract_paths_and_extensions(image_path):
        file_name, extension = os.path.splitext(image_path)
        root_path = os.path.dirname(image_path)

        return file_name, extension, root_path


class HistogramEqualisation(Operation):
    def __init__(self, probability):
        Operation.__init__(self, probability)

    def perform_operation(self, image):
        # TODO: We may need to apply this to each channel:
        # This might be a color image.
        # The histogram will be computed on the flattened image.
        # You can instead apply this function to each color channel.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ImageOps.equalize(image)


class Greyscale(Operation):
    def __init__(self, probability):
        Operation.__init__(self, probability)

    def perform_operation(self, image):
        return ImageOps.grayscale(image)


class Invert(Operation):
    def __init__(self, probability):
        Operation.__init__(self, probability)

    def perform_operation(self, image):
        return ImageOps.invert(image)


class BlackAndWhite(Operation):
    def __init__(self, probability):
        Operation.__init__(self, probability)

    def perform_operation(self, image):
        # TODO: Currently this has been taken from URL below, needs to be changed anyway.
        # http://stackoverflow.com/questions/18777873/convert-rgb-to-black-or-white
        image = ImageOps.grayscale(image)
        image = image.point(lambda x: 0 if x < 128 else 255, '1')
        return image


class Skew(Operation):
    """
    Perform perspective skewing on images.
    """
    def __init__(self, probability, magnitude):
        Operation.__init__(self, probability)
        self.magnitude = magnitude

    def perform_operation(self, image):
        """
        Skew an image across 4 points.
        :param image: The image to transform.
        :return: The transformed image.
        """

        # Use PIL to do this by generating the transform matrix

        skew_matrix = [0,0, 1,100, 100,1, 100,100]

        # To calculate the coefficients required by PIL for the perspective skew,
        # see the following Stack Overflow discussion: https://goo.gl/sSgJdj

        return image.transform(image.size, Image.PERSPECTIVE, skew_matrix, resample=Image.BICUBIC)


class Rotate(Operation):
    def __init__(self, probability, rotation):
        Operation.__init__(self, probability)
        self.rotation = rotation

    def __str__(self):
        return "Rotate " + str(self.rotation)

    def perform_operation(self, image):
        """
        Rotate an image by an arbitrary amount.

        :param image: The image to rotate.
        :return: The rotated image.
        """
        if self.rotation == -1:
            random_factor = random.randint(1, 3)
            # TODO: Check if for a modulo 90 a resample is needed
            return image.rotate(90 * random_factor, expand=True, resample=Image.BICUBIC)
        else:
            # Get size before we rotate
            x = image.size[0]
            y = image.size[1]

            # Rotate, while expanding the canvas size
            image = image.rotate(self.rotation, expand=True, resample=Image.BICUBIC)

            # Get size after rotation, which includes the empty space
            X = image.size[0]
            Y = image.size[1]

            # Get our two angles needed for the calculation of the largest area
            angle_a = abs(self.rotation)
            angle_b = 90 - angle_a

            # Python deals in radians so get our radians
            angle_a_rad = math.radians(angle_a)
            angle_b_rad = math.radians(angle_b)

            # Find the maximum area of the rectangle that could be cropped
            E = (math.sin(angle_a_rad)) / (math.sin(angle_b_rad)) * \
                (Y - X * (math.sin(angle_a_rad) / math.sin(angle_b_rad)))
            E = E / 1 - (math.sin(angle_a_rad) ** 2 / math.sin(angle_b_rad) ** 2)
            B = X - E
            A = (math.sin(angle_a_rad) / math.sin(angle_b_rad)) * B

            # Crop this area from the rotated image
            image = image.crop((E, A, X - E, Y - A))

            # Return the image, re-sized to the size of the image passed originally
            return image.resize((x, y), resample=Image.BICUBIC)


class RotateRange(Operation):
    def __init__(self, probability, rotate_range):
        Operation.__init__(self, probability)
        self.max_left_rotation = -abs(rotate_range[0])  # Ensure always negative
        self.max_right_rotation = abs(rotate_range[1])  # Ensure always positive

    def perform_operation(self, image):
        # This may be of use: http://stackoverflow.com/questions/34747946/rotating-a-square-in-pil
        random_left = random.randint(self.max_left_rotation, -1)
        random_right = random.randint(1, self.max_right_rotation)

        left_or_right = random.randint(0, 1)

        if left_or_right == 0:
            return image.rotate(random_left)
        elif left_or_right == 1:
            return image.rotate(random_right)


class Resize(Operation):
    def __init__(self, probability, width, height, resample_filter):
        Operation.__init__(self, probability)
        self.width = width
        self.height = height
        self.resample_filter = resample_filter

    def perform_operation(self, image):
        # TODO: Automatically change this to ANTIALIAS or BICUBIC depending on the size of the file
        return image.resize((self.width, self.height), eval("Image.%s" % self.resample_filter))


class Flip(Operation):
    def __init__(self, probability, top_bottom_left_right):
        Operation.__init__(self, probability)
        self.top_bottom_left_right = top_bottom_left_right

    def perform_operation(self, image):
        if self.top_bottom_left_right == "LEFT_RIGHT":
            return image.transpose(Image.FLIP_LEFT_RIGHT)
        elif self.top_bottom_left_right == "TOP_BOTTOM":
            return image.transpose(Image.FLIP_TOP_BOTTOM)
        elif self.top_bottom_left_right == "RANDOM":
            random_axis = random.randint(0, 1)
            if random_axis == 0:
                return image.transpose(Image.FLIP_LEFT_RIGHT)
            elif random_axis == 1:
                return image.transpose(Image.FLIP_TOP_BOTTOM)


class Crop(Operation):
    def __init__(self, probability, width, height, centre):
        Operation.__init__(self, probability)
        self.width = width
        self.height = height
        self.centre = centre

    def perform_operation(self, image):

        w, h = image.size

        if self.centre:
            new_width = self.width / 2.
            new_height = self.height / 2.
            half_the_width = w / 2
            half_the_height = h / 2

            return image.crop(
                (
                    half_the_width - ceil(new_width),
                    half_the_height - ceil(new_height),
                    half_the_width + floor(new_width),
                    half_the_height + floor(new_height)
                )
            )
        else:
            random_right_shift = random.randint(0, (w - self.width))
            random_down_shift = random.randint(0, (h - self.height))

            return image.crop(
                (
                    random_right_shift,
                    random_down_shift,
                    self.width+random_right_shift,
                    self.height+random_down_shift
                )
            )


class CropPercentage(Operation):
    def __init__(self, probability, percentage_area, centre):
        Operation.__init__(self, probability)
        self.percentage_area = percentage_area
        self.centre = centre

    def perform_operation(self, image):
        w, h = image.size
        w_new = int(floor(w * self.percentage_area))  # TODO: Floor might return 0, so we need to check this.
        h_new = int(floor(h * self.percentage_area))

        if self.centre:
            left_shift = floor(w_new / 2.)
            down_shift = floor(h_new / 2.)
            return image.crop((left_shift, down_shift, w_new + left_shift, h_new + down_shift))
        else:
            random_left_shift = random.randint(0, (w - w_new))  # Note: randint() is from uniform distribution.
            random_down_shift = random.randint(0, (h - h_new))
            return image.crop((random_left_shift, random_down_shift, w_new + random_left_shift, h_new + random_down_shift))


class CropRandom(Operation):
    def __init__(self, probability, percentage_area):
        Operation.__init__(self, probability)
        self.percentage_area = percentage_area

    def perform_operation(self, image):
        w, h = image.size

        # TODO: Fix this, as it is currently 1/4 of the area for 0.5 rather than 1/2.
        w_new = int(floor(w * self.percentage_area))  # TODO: Floor might return 0, so we need to check this.
        h_new = int(floor(h * self.percentage_area))

        random_left_shift = random.randint(0, (w - w_new))  # Note: randint() is from uniform distribution.
        random_down_shift = random.randint(0, (h - h_new))

        return image.crop((random_left_shift, random_down_shift, w_new + random_left_shift, h_new + random_down_shift))


class Shear(Operation):
    def __init__(self, probability, max_shear_left, max_shear_right):
        Operation.__init__(self, probability)
        # This is in radians, see
        # http://scikit-image.org/docs/dev/api/skimage.transform.html
        self.max_shear_left = max_shear_left
        self.max_shear_right = max_shear_right

    def perform_operation(self, image):

        ######################################################################
        # Old version which uses SciKit Image
        ######################################################################
        # We will use scikit-image for this so first convert to a matrix
        # using NumPy
        # amount_to_shear = round(random.uniform(self.max_shear_left, self.max_shear_right), 2)
        # image_array = np.array(image)
        # And here we are using SciKit Image's `transform` class.
        # shear_transformer = transform.AffineTransform(shear=amount_to_shear)
        # image_sheared = transform.warp(image_array, shear_transformer)

        # Because of warnings
        # with warnings.catch_warnings():
        #     warnings.simplefilter("ignore")
        #     return Image.fromarray(img_as_ubyte(image_sheared))
        ######################################################################

        width, height = image.size

        angle_to_shear = int(random.uniform(self.max_shear_left, self.max_shear_right))

        phi = math.tan(math.radians(angle_to_shear))

        # Here we need the unknown b, where a is
        # the height of the image and phi is the
        # angle we want to shear (our knowns):
        # b = tan(phi) * a
        shift_in_pixels = phi * height

        # Transformation matrices can be found here:
        # https://en.wikipedia.org/wiki/Transformation_matrix
        # The PIL affine transform expects the first two rows of
        # any of the affine transformation matrices, seen here:
        # https://en.wikipedia.org/wiki/Transformation_matrix#/media/File:2D_affine_transformation_matrix.svg

        # Note: PIL expects the inverse scale, so 1/scale_factor for example.
        return image.transform((int(round(width + shift_in_pixels)), height),
                               Image.AFFINE,
                               (1, phi, -shift_in_pixels,
                                0, 1, 0),
                               Image.BICUBIC)


class Scale(Operation):
    """
    Class to increase or decrease images by a certain factor. The ``Resize`` class handles images \
    that need to be re-sized with different **dimensions**, which may not maintain aspect ratio.
    """
    def __init__(self, probability, scale_factor):
        Operation.__init__(self, probability)
        self.scale_factor = scale_factor

    # Resize by a certain factor (*not* dimensions - which would uniformly resize all
    # images to X*Y while scale depends on the size of the input)
    def perform_operation(self, image):
        h, w = image.size
        new_h = h * int(floor(self.scale_factor))
        new_w = w * int(floor(self.scale_factor))
        return image.resize((new_w, new_h))


class Distort(Operation):
    def __init__(self, probability, grid_width, grid_height, magnitude, randomise_magnitude):
        Operation.__init__(self, probability)
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.magnitude = abs(magnitude)
        randomise_magnitude = True  # TODO: Fix code below to handle FALSE state.
        self.randomise_magnitude = randomise_magnitude

    def perform_operation(self, image):

        w, h = image.size

        horizontal_tiles = self.grid_width
        vertical_tiles = self.grid_height

        width_of_square = int(floor(w / float(horizontal_tiles)))
        height_of_square = int(floor(h / float(vertical_tiles)))

        width_of_last_square = w - (width_of_square * (horizontal_tiles - 1))
        height_of_last_square = h - (height_of_square * (vertical_tiles - 1))

        dimensions = []

        for vertical_tile in range(vertical_tiles):
            for horizontal_tile in range(horizontal_tiles):
                if vertical_tile == (vertical_tiles - 1) and horizontal_tile == (horizontal_tiles - 1):
                    dimensions.append([horizontal_tile * width_of_square,
                                       vertical_tile * height_of_square,
                                       width_of_last_square + (horizontal_tile * width_of_square),
                                       height_of_last_square + (height_of_square * vertical_tile)])
                elif vertical_tile == (vertical_tiles - 1):
                    dimensions.append([horizontal_tile * width_of_square,
                                       vertical_tile * height_of_square,
                                       width_of_square + (horizontal_tile * width_of_square),
                                       height_of_last_square + (height_of_square * vertical_tile)])
                elif horizontal_tile == (horizontal_tiles - 1):
                    dimensions.append([horizontal_tile * width_of_square,
                                       vertical_tile * height_of_square,
                                       width_of_last_square + (horizontal_tile * width_of_square),
                                       height_of_square + (height_of_square * vertical_tile)])
                else:
                    dimensions.append([horizontal_tile * width_of_square,
                                       vertical_tile * height_of_square,
                                       width_of_square + (horizontal_tile * width_of_square),
                                       height_of_square + (height_of_square * vertical_tile)])

        # For loop that generates polygons could be rewritten, but maybe harder to read?
        # polygons = [x1,y1, x1,y2, x2,y2, x2,y1 for x1,y1, x2,y2 in dimensions]

        # last_column = [(horizontal_tiles - 1) + horizontal_tiles * i for i in range(vertical_tiles)]
        last_column = []
        for i in range(vertical_tiles):
            last_column.append((horizontal_tiles-1)+horizontal_tiles*i)

        last_row = range((horizontal_tiles * vertical_tiles) - horizontal_tiles, horizontal_tiles * vertical_tiles)

        polygons = []
        for x1, y1, x2, y2 in dimensions:
            polygons.append([x1, y1, x1, y2, x2, y2, x2, y1])

        polygon_indices = []
        for i in range((vertical_tiles * horizontal_tiles) - 1):
            if i not in last_row and i not in last_column:
                polygon_indices.append([i, i + 1, i + horizontal_tiles, i + 1 + horizontal_tiles])

        for a, b, c, d in polygon_indices:
            dx = random.randint(-self.magnitude, self.magnitude)
            dy = random.randint(-self.magnitude, self.magnitude)

            x1, y1, x2, y2, x3, y3, x4, y4 = polygons[a]
            polygons[a] = [x1, y1,
                           x2, y2,
                           x3 + dx, y3 + dy,
                           x4, y4]

            x1, y1, x2, y2, x3, y3, x4, y4 = polygons[b]
            polygons[b] = [x1, y1,
                           x2 + dx, y2 + dy,
                           x3, y3,
                           x4, y4]

            x1, y1, x2, y2, x3, y3, x4, y4 = polygons[c]
            polygons[c] = [x1, y1,
                           x2, y2,
                           x3, y3,
                           x4 + dx, y4 + dy]

            x1, y1, x2, y2, x3, y3, x4, y4 = polygons[d]
            polygons[d] = [x1 + dx, y1 + dy,
                           x2, y2,
                           x3, y3,
                           x4, y4]

        generated_mesh = []
        for i in range(len(dimensions)):
            generated_mesh.append([dimensions[i], polygons[i]])

        return image.transform(image.size, Image.MESH, generated_mesh, resample=Image.LINEAR)


class Zoom(Operation):
    # TODO: Zoom dimensions and do not crop, so that the crop can be applied manually later
    def __init__(self, probability, min_factor, max_factor):
        Operation.__init__(self, probability)
        self.min_factor = min_factor
        self.max_factor = max_factor

    def perform_operation(self, image):
        factor = round(random.uniform(self.min_factor, self.max_factor), 2)
        original_width, original_height = image.size
        # TODO: Join these two functions together so that we don't have this image_zoom variable lying around.
        image_zoomed = image.resize((int(round(image.size[0] * factor)), int(round(image.size[1] * factor))))

        # Return the centre of the zoomed image, so that it is the same dimensions as the original image
        half_the_width = image_zoomed.size[0] / 2
        half_the_height = image_zoomed.size[1] / 2
        return image_zoomed.crop(
            (
                half_the_width - ceil((original_width / 2.)),
                half_the_height - ceil((original_height / 2.)),
                half_the_width + floor((original_width / 2.)),
                half_the_height + floor((original_height / 2.))
            )
        )


class Custom(Operation):
    """
    Class that allows for a custom operation to be performed.
    """
    def __init__(self, probability, custom_function, **function_arguments):
        """
        Creates a custom operation that can be added to a pipeline.

        To add a custom operation you can instantiate this class, passing
        a function pointer, :attr:`custom_function`, followed by an
        arbitrarily long list keyword arguments, :attr:`**function_arguments`.

        .. seealso:: The :func:`~Augmentor.Pipeline.Pipeline.add_operation`
         function.

        :param probability: The probability that the operation will be
         performed.
        :param custom_function: The name of the function that performs your
         custom code. Must return an Image object and accept an Image object
         as its first parameter.
        :param function_arguments: The arguments for your custom operation's
         code.
         :type probability: Float
         :type custom_function: *Function
         :type function_arguments: dict
        """
        Operation.__init__(self, probability)
        self.custom_function = custom_function
        self.function_arguments = function_arguments
        # TODO: find the names of the argument types above, is that a function pointer???

    def __str__(self):
        return "Custom (" + self.custom_function.__name__ + ")"

    def perform_operation(self, image):
        return self.function_name(image, **self.function_arguments)
