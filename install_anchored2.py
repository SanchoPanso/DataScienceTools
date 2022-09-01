import os
import cv2
import numpy as np
from extractor import Extractor
from installer import Installer


def merge_images(src_dir1, src_dir2, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)

    files1 = os.listdir(src_dir1)
    files2 = os.listdir(src_dir2)

    files1.sort()
    files2.sort()

    for file in files1:
        img = cv2.imread(os.path.join(src_dir1, file))
        cv2.imwrite(os.path.join(dst_dir, file.split('.')[0] + '_1.jpg'), img)

    for file in files2:
        img = cv2.imread(os.path.join(src_dir2, file))
        cv2.imwrite(os.path.join(dst_dir, file.split('.')[0] + '_2.jpg'), img)


def change_image_name(data: dict, postfix: str) -> dict:
    images = list(data['annotations'].keys())
    for image in images:
        name, ext = os.path.splitext(image)
        new_image = name + postfix + ext
        data['annotations'][new_image] = data['annotations'].pop(image)
    return data


def change_classes(data: dict, change_dict: dict, new_classes: list) -> dict:
    data['classes'] = new_classes
    for key in data['annotations'].keys():
        lines = data['annotations'][key]
        new_lines = []

        for line in lines:
            new_line = line
            if change_dict[line[0]] is not None:
                new_line[0] = change_dict[line[0]]
                new_lines.append(new_line)
        data['annotations'][key] = new_lines
    return data


if __name__ == '__main__':
    datasets_dir = os.path.join('E:\\PythonProjects', 'AnnotationConverter', 'datasets')
    downloads_dir = os.path.join('C:\\Users', 'Alex', 'Downloads')

    defects_merged_dir = os.path.join(datasets_dir, 'defects_merged_05082022')
    defects_joint_exposure_dir = os.path.join(datasets_dir, 'defects_joint_exposure')
    defects_tube_dir = os.path.join(datasets_dir, 'defects_16082022')


    extractor = Extractor()
    data1 = extractor.extract(r'C:\Users\Alex\Downloads\csv1_comet_1_12_08\annotations\instances_default.json')
    data2 = extractor.extract(r'C:\Users\Alex\Downloads\csv1_comet_2_11_08\annotations\instances_default.json')

    data1 = change_image_name(data1, '_1')
    data2 = change_image_name(data2, '_2')

    data = data1
    data['annotations'].update(data2['annotations'])

    changes = {
        0: None,
        1: None,
        2: None,
        3: None,
        4: 0,
        5: None,
        6: None,
        7: None,
    }
    data = change_classes(data, changes, ['tube'])
    print(data['annotations'].keys())

    installer = Installer()
    installer.install_with_anchor(data, defects_merged_dir, defects_tube_dir, defects_joint_exposure_dir)



