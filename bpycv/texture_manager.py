#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import bpy
import boxx
from boxx import *
from boxx import os, setTimeout, mapmt, timegap, sleep, pathjoin

import random
import glob

from bs4 import BeautifulSoup
import requests
import urllib.parse as urlparse
import json

bs = BeautifulSoup
rq = requests


class TextureManager:
    def __init__(
        self,
        tex_dir="./bpycv_tex_cache",
        resolution="4k",
        category="all",
        download=False,
        debug=False,
    ):
        """
        Download and manage hdri file from https://polyhaven.com/textures/

        Parameters
        ----------
        tex_dir : str, optional
            hdri dir. The default is "./bpycv_tex_cache".
        resolution : str, optional
            choice [1k, 2k, 4k, 8k, 16k, 19k]. The default is "4k".
        category : str, optional
            refer to https://polyhaven.com/textures/ side bar. Use comma to separate multiple categories.
            The default is "all".
        download : bool, optional
            If True, auto download from https://polyhaven.com/textures/
            by another threading using requesets.
            The default is False.
        """
        self.resolution = resolution
        self.category = category.lower().replace("/", "-")
        self.tex_dir = tex_dir
        os.makedirs(tex_dir, exist_ok=True)
        self.downloading = download
        self.debug = debug
        if self.downloading:
            print('Starting download texture file from "polyhaven.com" in side threads')
            if debug:
                self.prepare()
            else:
                setTimeout(self.prepare)
        self.set_tex_paths()

    def set_tex_paths(self):
        self.all_paths = sorted(
            sum(
                [
                    glob.glob(os.path.join(self.tex_dir, "*/*.blend"))
                ],
                [],
            )
        )
        assert self.downloading or len(self.all_paths)
        if not len(self.all_paths):
            self.tex_paths = []
            return
        if self.category == "all":
            self.tex_paths = sorted(self.all_paths)
            return

        listt = []
        for path in self.all_paths:
            fname = boxx.filename(path)
            dirname = os.path.basename(os.path.dirname(path))
            name = fname.split(".")[0]
            listt.append(
                dict(
                    name=name,
                    res=name.split("_")[-1],
                    cats=dirname.split(".")[1].split("="),
                    tags=dirname.split(".")[2].split("="),
                    path=path,
                )
            )
        self.df = boxx.pd.DataFrame(listt)
        tex_paths = self.df[self.df.cats.apply(lambda cats: self.category in cats)].path
        self.tex_paths = sorted(tex_paths)

    def __len__(self):
        if self.downloading:
            self.set_tex_paths()
        return len(self.tex_paths)

    def __getitem__(self, i):
        if self.downloading:
            self.set_tex_paths()
        return self.tex_paths[i]

    def sample(self):
        if self.downloading:
            self.set_tex_paths()
        while not len(self.tex_paths):
            assert (
                self.downloading
            ), f'No texture file in "{self.tex_dir}", make sure TextureManager(download=True)'
            self.set_tex_paths()
            if timegap(5, 'waiting for download texture file'):
                print('Waiting for download first texture file....')
            sleep(0.1)
        return random.choice(self.tex_paths)

    def prepare(
        self,
    ):
        resolution = self.resolution
        category = self.category
        tex_dir = self.tex_dir

        url = f"https://api.polyhaven.com/assets?t=textures&c={category}"
        page = rq.get(url, timeout=5)
        data = page.json()
        names = list(data.keys())

        def download(name):
            t = 60
            while 1:
                try:
                    if self.debug:
                        print(name)
                    prefix = f"{name}_{resolution}"
                    paths = boxx.glob(os.path.join(tex_dir, prefix + "*.blend"))
                    if len(paths):
                        return paths[0]

                    url = f"https://polyhaven.com/a/{name}"
                    html = BeautifulSoup(
                        rq.get(url, timeout=5).text,
                        features="html.parser",
                    )
                    script_tag = json.loads(html.find('script', {'id': '__NEXT_DATA__'}).text)
                    cats = ["category"] + script_tag["props"]["pageProps"]["data"]["categories"]
                    tags = ["tags"] + script_tag["props"]["pageProps"]["data"]["tags"]
                    subdir = pathjoin(tex_dir, f"{prefix}.{'='.join(cats)}.{'='.join(tags)}")                    

                    for include_tex_path, include_tex_data in script_tag["props"]["pageProps"]["files"]["blend"][resolution]["blend"]["include"].items():
                        href = include_tex_data["url"]
                        r = rq.get(href, timeout=5)
                        assert r.status_code == 200
                        path = pathjoin(subdir, include_tex_path)
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, "wb") as f:
                            f.write(r.content)

                    blend_href = script_tag["props"]["pageProps"]["files"]["blend"][resolution]["blend"]["url"]
                    blend_filename = f"{name}.blend"
                    blend_path = pathjoin(subdir, blend_filename)
                    r = rq.get(blend_href, timeout=5)
                    assert r.status_code == 200
                    with open(blend_path, "wb") as f:
                        f.write(r.content)
                    return blend_path
                except AssertionError:
                    print(f"r.status_code = {r.status_code}, sleep({t})")
                    sleep(t)
                    t *= 2
                except Exception as e:
                    if self.debug:
                        boxx.pred - name
                        boxx.g()
                    raise e

        _names = names[:]
        random.shuffle(_names)
        if self.debug:
            list(
                map(
                    download,
                    _names,
                )
            )
        else:
            mapmt(download, _names, pool=1)
        self.set_tex_paths()
        self.downloading = False
        print("Download texture threads has finished!")
    
    @classmethod
    def load_texture(path):
        mat_name = os.path.basename(path).split(".")[0]
        with bpy.data.libraries.load(path) as (data_from, data_to):
            data_to.materials = data_from.materials
        return bpy.data.materials[mat_name]

    @classmethod
    def test(cls):
        tex_dir = "/tmp/tex"
        tm = TextureManager(
            tex_dir=tex_dir, category="wood,clean", download=False, debug=True
        )
        for i in range(10):
            tex = tm.sample()
            print(tex)
            assert tm.category in tex
        boxx.g()
    
    def load_texture(self, texture_name):
        pass


if __name__ == "__main__":
    tex_dir = "/tmp/tex"
    tm = TextureManager(tex_dir=tex_dir, download=True, debug=True)
    tex = tm.sample()
    print(tex)
